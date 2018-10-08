from IStorage import IStorage, AlreadyPersistentError
from hecuba import config, log
from collections import namedtuple
import re
import uuid

class Iterator:

    def __init__(self, iterator):
        self.iterator = iterator

    def __iter__(self):
        return self

    def next(self):
        return (next(self.iterator))[0]


class StorageSet(set, IStorage):
    args_names = ["name", "column", "tokens", "storage_id", "indexed_on", "istorage_props", "class_name"]
    args = namedtuple('StorageSetArgs', args_names)
    _prepared_store_meta = config.session.prepare('INSERT INTO hecuba' +
                                                  '.istorage (storage_id, class_name, name, tokens, istorage_props) '
                                                  ' VALUES (?,?,?,?,?)')
    """
    This class is where information will be stored in Hecuba.
    The information can be in memory, stored in a python dictionary or local variables, or saved in a
    DB(Cassandra), depending on if it's persistent or not.
    """

    @staticmethod
    def build_remotely(new_args):
        """
            Launches the StorageSet.__init__ from the uuid api.getByID
            Args:
                new_args: a list of all information needed to create again the storageset
            Returns:
                so: the created storageset
        """
        log.debug("Building Storage object with %s", new_args)
        class_name = new_args.class_name
        if class_name is 'StorageSet':
            so = StorageSet(new_args.name.encode('utf8'), new_args.tokens, new_args.storage_id, new_args.istorage_props)

        else:
            class_name, mod_name = IStorage.process_path(class_name)
            mod = __import__(mod_name, globals(), locals(), [class_name], 0)

            so = getattr(mod, class_name)(new_args.name.encode('utf8'), new_args.tokens,
                                          new_args.storage_id, new_args.istorage_props)

        return so

    @staticmethod
    def _store_meta(storage_args):
        """
            Saves the information of the object in the istorage table.
            Args:
                storage_args (object): contains all data needed to restore the object from the workers
        """
        log.debug("StorageSet: storing media %s", storage_args)
        try:

            config.session.execute(StorageSet._prepared_store_meta,
                                   [storage_args.storage_id,
                                    storage_args.class_name,
                                    storage_args.name,
                                    storage_args.tokens,
                                    storage_args.istorage_props])
        except Exception as ex:
            log.warn("Error creating the StorageDict metadata: %s, %s", str(storage_args), ex)
            raise ex

    _set_case = re.compile('.*@TypeSpec +(\w+)')
    _dict_case = re.compile('.*@TypeSpec +(\w+) +dict+ *< *< *([\w:, ]+)+ *> *, *([\w+:., <>]+) *>')
    _tuple_case = re.compile('.*@TypeSpec +(\w+) +tuple+ *< *([\w, +]+) *>')
    _index_vars = re.compile('.*@Index_on *([A-z0-9]+) +([A-z0-9, ]+)')

    def __init__(self, name="", column=None, tokens=None, storage_id=None, indexed_args=None, istorage_props=None, **kwargs):
        """
            Creates a new storageset.
            Args:
                name (string): the name of the Cassandra Keyspace + table where information can be found
                tokens (list of tuples): token ranges assigned to the new StorageSet
                storage_id (string):  an unique storageset identifier
                istorage_props dict(string,string): a map with the storage id of each contained istorage object.
                kwargs: more optional parameters
        """
        super(StorageSet, self).__init__(**kwargs)
        log.debug("CREATED StorageSet(%s)", name)
        self._is_persistent = False
        self._storage_id = storage_id
        self._istorage_props = istorage_props
        self._tokens = tokens
        self._ksp, self._table = self._extract_ks_tab(name)
        self._class_name = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)

        if tokens is None:
            log.info('using all tokens')
            tokens = map(lambda a: a.value, config.cluster.metadata.token_map.ring)
            self._tokens = IStorage._discrete_token_ranges(tokens)
        else:
            self._tokens = tokens

        if self.__doc__ is not None:
            self._persistent_props = self._parse_comments(self.__doc__)
            self._persistent_attrs = self._persistent_props.keys()
            # self._column = self._persistent_props[self.__class__.__name__]['column']
            # temporal para debug
            self._column = self._persistent_props['column']

            try:
                self._indexed_args = self._persistent_props[self.__class__.__name__]['indexed_values']
            except KeyError:
                self._indexed_args = indexed_args

        else:
            self._column = column
            self._indexed_args = indexed_args

        class_name = '%s.%s' % (self.__class__.__module__, self.__class__.__name__)
        self._build_args = self.args(None, self._column, self._tokens,
                                     self._storage_id, self._indexed_args, self._istorage_props, class_name)

        if name:
            self._setup_persistent_structs()
            self._store_meta(self._build_args)
        else:
            self._is_persistent = False

    @classmethod
    def _parse_comments(cls, comments):
        """
            Parses de comments in a class file to save them in the class information
            Args:
                comments: the comment in the class file
            Returns:
                this: a structure with all the information of the comment
        """
        this = {}
        for line in comments.split('\n'):
            m = StorageSet._set_case.match(line)
            if m is not None:
                # Matching TypeSpec of a Set
                set_types = m.groups()
                set_type = set_types[0]

                set_type_cassandra = StorageSet._conversions[set_type]

                # TODO implement sets with tuples
                # name = str(cls)
                if cls.__class__.__name__ in this:
                    this.update({'type': 'set', 'column': set_type_cassandra})
                else:
                    this = {
                        'type': 'set',
                        'column': set_type_cassandra}
            '''
            m = StorageSet._index_vars.match(line)
            if m is not None:
                table_name, indexed_values = m.groups()
                indexed_values = indexed_values.replace(' ', '').split(',')
                if table_name in this:
                    this[table_name].update({'indexed_values': indexed_values})
                else:
                    this[table_name] = {'indexed_values': indexed_values}
            '''
        return this

    def make_persistent(self, name):
        """
        Method to transform a StorageSet into a persistent object.
        This will make it use a persistent DB as the main location
        of its data.
        Args:
            name (string): name with which the table in the DB will be created
        """

        if self._is_persistent:
            raise AlreadyPersistentError("This StorageObj is already persistent [Before:{}.{}][After:{}]",
                                         self._ksp, self._table, name)

        (self._ksp, self._table) = self._extract_ks_tab(name)
        self._setup_persistent_structs()

    def add(self, value):
        """
           Method to insert values in the StorageSet
           Args:
               val: the value that we want to save
        """

        if self._is_persistent:
            query = "INSERT INTO %s.%s (column, empty_column)" % (self._ksp, self._table)
            if isinstance(value, str) or isinstance(value, unicode):
                query += " VALUES ('%s', ' ')" % value
            else:
                query += " VALUES (%s, ' ')" % value
            config.session.execute(query)

        set.add(self, value)

    def remove(self, value):
        """
           Method to delete values in the StorageSet
           Args:
               val: the value that we want to delete
        """
        if self._is_persistent:
            query = "DELETE FROM %s.%s WHERE column = " % (self._ksp, self._table)
            if isinstance(value, str) or isinstance(value, unicode):
                query += "'%s'" % value
            else:
                query += str(value)
            config.session.execute(query)

        set.remove(self, value)

    def __contains__(self, value):
        """
           Method to check if a given value is in the StorageSet
           Args:
               val: the value that we want to check
        """

        if self._is_persistent:
            query = "SELECT count(*) FROM %s.%s WHERE column = " % (self._ksp, self._table)
            if isinstance(value, str) or isinstance(value, unicode):
                query += "'%s'" % value
            else:
                query += str(value)
            result = config.session.execute(query)
            # result[0] is the first row (will be only on row) and result[0][0] is the count
            return result[0][0]
        else:
            return set.__contains__(self, value)

    def union(self, storageSet):
        if not isinstance(storageSet, StorageSet):
            raise Exception("Expected StorageSet argument")

        if not self._is_persistent:
            set.union(self, set(storageSet))
        else:
            if not storageSet._is_persistent:
                for value in storageSet:
                    self.add(value)
            else:
                # regular case, two persistent sets
                ps = config.session.prepare(
                    "INSERT INTO %s.%s (column, empty_column) VALUES (?, ' ')" % (self._ksp, self._table))
                for value in storageSet:
                    config.session.execute(ps, [value])

    def intersection(self, storageSet):
        if not isinstance(storageSet, StorageSet):
            raise Exception("Expected StorageSet argument")

        if not self._is_persistent:
            if not storageSet._is_persistent:
                set.intersection(self, set(storageSet))
        else:
            if not storageSet._is_persistent:
                for value in self:
                    if value not in storageSet:
                        self.remove(value)
            else:
                # regular case, two persistent sets
                # ps = "INSERT INTO %s.%s (column, empty_column) VALUES (?, ' ')" % (self._ksp, self._table)
                # print(ps)
                ps = config.session.prepare("DELETE FROM %s.%s WHERE column = ?" % (self._ksp, self._table))
                for value in self:
                    if value not in storageSet:
                        config.session.execute(ps, [value])

    def clear(self):
        if self._is_persistent:
            query = "TRUNCATE %s.%s" % (self._ksp, self._table)
            config.session.execute(query)

        set.clear(self)

    def __iter__(self):
        if self._is_persistent:
            query = "SELECT column FROM %s.%s " % (self._ksp, self._table)
            result = config.session.execute(query)
            return Iterator(iter(result))
        else:
            return set.__iter__(self)

    def __len__(self):
        if self._is_persistent:
            query = "SELECT count(*) FROM %s.%s " % (self._ksp, self._table)
            result = config.session.execute(query)
            return result[0][0]
        else:
            return len(set(self))


    def _setup_persistent_structs(self):
        """
            Setups the python structures used to communicate with the backend.
            Creates the necessary tables on the backend to store the object data.
        """

        self._is_persistent = True

        if self._storage_id is None:
            self._storage_id = uuid.uuid3(uuid.NAMESPACE_DNS, self._ksp + '.' + self._table)

        self._build_args = self._build_args._replace(storage_id=self._storage_id)
        self._store_meta(self._build_args)

        query_keyspace = "CREATE KEYSPACE IF NOT EXISTS %s WITH replication = %s" % (self._ksp, config.replication)
        try:
            config.session.execute(query_keyspace)
        except Exception as ex:
            log.warn("Error creating the StorageSet keyspace %s, %s", (query_keyspace), ex)
            raise ex

        # drop = 'DROP TABLE IF EXISTS %s.%s' % (self._ksp, self._table)
        # config.session.execute(drop)
        query_simple = 'CREATE TABLE IF NOT EXISTS ' + self._ksp + '.' + self._table + \
                       '( '

        query_simple += "column "
        query_simple += self._persistent_props['column'] + " PRIMARY KEY, empty_column text, "

        try:
            config.session.execute(query_simple[:-2] + ' )')

        except Exception as ir:
            log.error("Unable to execute %s", query_simple)
            raise ir

    def stop_persistent(self):
        """
            The StorageSet stops being persistent, but keeps the information already stored in Cassandra
        """
        log.debug("STOP PERSISTENT")
        self._is_persistent = False

    def delete_persistent(self):
        """
            Deletes the Cassandra table where the persistent StorageSet stores data
        """
        query = "TRUNCATE TABLE %s.%s;" % (self._ksp, self._table)
        log.debug("DELETE PERSISTENT: %s", query)
        config.session.execute(query)

        self._is_persistent = False

    def __setattr__(self, attribute, value):
        """
            Given a key and its value, this function saves it (depending on if it's persistent or not):
                a) In memory
                b) In the DB
            Args:
                attribute: name of the value that we want to set
                value: value that we want to save
        """
        if attribute[0] is '_' or attribute not in self._persistent_attrs:
            object.__setattr__(self, attribute, value)
            return

        if config.hecuba_type_checking and value is not None and not isinstance(value, dict) and \
                IStorage._conversions[value.__class__.__name__] != self._persistent_props[attribute]['type']:
            raise TypeError
