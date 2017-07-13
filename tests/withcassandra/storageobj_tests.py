import unittest
import uuid
import time
from hecuba.IStorage import IStorage
from app.words import Words
from hecuba import config
from hecuba.storageobj import StorageObj
import cassandra
from storage.api import getByID


class Result(StorageObj):
    '''
    @ClassField instances dict<<word:str>,numinstances:int>
    '''
    pass


class TestStorageObj(StorageObj):
    '''
       @ClassField test dict<<position:int>,text:str>
    '''
    pass


class TestStorageIndexedArgsObj(StorageObj):
    '''
       @ClassField test dict<<position:int>,x:float,y:float,z:float>
       @Index_on test x,y,z
    '''
    pass


class Test2StorageObj(StorageObj):
    '''
       @ClassField name str
       @ClassField age int
    '''
    pass


class Test3StorageObj(StorageObj):
    '''
       @ClassField myso tests.withcassandra.storageobj_tests.Test2StorageObj
       @ClassField myso2 tests.withcassandra.storageobj_tests.TestStorageObj
       @ClassField myint int
       @ClassField mystr str
    '''
    pass


class Test4StorageObj(StorageObj):
    '''
       @ClassField myotherso tests.withcassandra.storageobj_tests.Test2StorageObj
    '''
    pass


class Test4bStorageObj(StorageObj):
    '''
       @ClassField myotherso tests.withcassandra.test2storageobj.Test2StorageObj
    '''
    pass


class Test5StorageObj(StorageObj):
    '''
       @ClassField test2 dict<<position:int>,myso:tests.withcassandra.storageobj_tests.Test2StorageObj>
    '''
    pass


class Test6StorageObj(StorageObj):
    '''
       @ClassField test3 dict<<int>,str,str>
    '''
    pass


class StorageObjTest(unittest.TestCase):
    def test_build_remotely(self):

        class res:
            pass

        r = res()
        r.ksp = config.execution_name
        r.name = 'tt1'
        r.class_name = str(TestStorageObj.__module__) + "." + TestStorageObj.__name__
        r.tokens = IStorage._discrete_token_ranges(
            [8508619251581300691, 8514581128764531689, 8577968535836399533, 8596162846302799189,
             8603491526474728284, 8628291680139169981, 8687301163739303017, 9111581078517061776])
        r.storage_id = uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.tt1')
        r.istorage_props = {}
        nopars = StorageObj.build_remotely(r)
        self.assertEqual('tt1', nopars._table)
        self.assertEqual(config.execution_name, nopars._ksp)
        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.tt1'), nopars._storage_id)
        name, tkns = config.session.execute("SELECT name, tokens FROM hecuba.istorage WHERE storage_id = %s", [nopars._storage_id])[0]

        self.assertEqual(name, config.execution_name + '.tt1')
        self.assertEqual(tkns, r.tokens)

    def test_init_create_pdict(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tt1")
        config.session.execute("DROP TABLE IF EXISTS my_app.tt1_instances")

        class res:
            pass

        config.session.execute("DROP TABLE IF EXISTS "+config.execution_name + '.tt1')
        r = res()
        r.ksp = config.execution_name
        r.name = 'tt1'
        r.class_name = r.class_name = str(TestStorageObj.__module__) + "." + TestStorageObj.__name__
        r.storage_id = uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.' + r.name)
        r.tokens = IStorage._discrete_token_ranges(
            [8508619251581300691, 8514581128764531689, 8577968535836399533, 8596162846302799189,
             8603491526474728284, 8628291680139169981, 8687301163739303017, 9111581078517061776])
        r.istorage_props = {}
        nopars = StorageObj.build_remotely(r)
        self.assertEqual('tt1', nopars._table)
        self.assertEqual(config.execution_name, nopars._ksp)
        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.tt1'), nopars._storage_id)
        name, tkns = \
            config.session.execute("SELECT name,tokens FROM hecuba.istorage WHERE storage_id = %s",
                                   [nopars._storage_id])[0]
        self.assertEqual(name, config.execution_name + '.' + r.name)
        self.assertEqual(tkns, r.tokens)

        tkns = IStorage._discrete_token_ranges(
            [8508619251581300691, 8514581128764531689, 8577968535836399533, 8596162846302799189,
             8603491526474728284, 8628291680139169981, 8687301163739303017, 9111581078517061776])
        config.session.execute("DROP TABLE IF EXISTS " + config.execution_name + '.tt2')
        nopars = Result(name='tt2',
                        tokens=tkns)
        self.assertEqual('tt2', nopars._table)
        self.assertEqual(config.execution_name, nopars._ksp)
        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.tt2'), nopars._storage_id)
        self.assertEqual(True, nopars._is_persistent)
        self.assertTrue(hasattr(nopars, 'instances'))
        name, read_tkns = config.session.execute("SELECT name,tokens FROM hecuba.istorage WHERE storage_id = %s",
                                                 [nopars._storage_id])[0]


        self.assertEqual(name, config.execution_name + '.tt2')
        self.assertEqual(tkns, read_tkns)

    def test_init_empty(self):
        config.session.execute("DROP TABLE IF EXISTS ksp1.ttta")
        nopars = TestStorageObj('ksp1.ttta')
        self.assertEqual('ttta', nopars._table)
        self.assertEqual('ksp1', nopars._ksp)

        res = config.session.execute(
            'SELECT storage_id, class_name, name, tokens, istorage_props FROM hecuba.istorage WHERE storage_id = %s',
            [nopars._storage_id])[0]

        storage_id, storageobj_classname, name, tokens, istorage_props = res
        self.assertEqual(storage_id, nopars._storage_id)
        self.assertEqual(storageobj_classname, TestStorageObj.__module__ + "." + TestStorageObj.__name__)
        self.assertEqual(name, 'ksp1.ttta')

        rebuild = StorageObj.build_remotely(res)
        self.assertEqual('ttta', rebuild._table)
        self.assertEqual('ksp1', rebuild._ksp)
        self.assertEqual(storage_id, rebuild._storage_id)

        self.assertEqual(nopars._is_persistent, rebuild._is_persistent)
        # self.assertEqual(vars(nopars), vars(rebuild))

    def test_make_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS hecuba_test.wordsso")
        config.session.execute("DROP TABLE IF EXISTS hecuba_test.nonames")
        config.session.execute("DROP TABLE IF EXISTS hecuba_test.words")
        config.session.execute("DROP TABLE IF EXISTS hecuba_test.wordsso_words")
        config.session.execute("DROP TABLE IF EXISTS hecuba_test.nonames_test3")
        nopars = Words()
        self.assertFalse(nopars._is_persistent)
        nopars.ciao = 1
        nopars.ciao2 = "1"
        nopars.ciao3 = [1, 2, 3]
        nopars.ciao4 = (1, 2, 3)
        for i in range(10):
            nopars.words[i] = 'ciao' + str(i)

        count, = config.session.execute(
            "SELECT count(*) FROM system_schema.tables WHERE keyspace_name = 'hecuba_test' and table_name = 'words'")[0]
        self.assertEqual(0, count)

        nopars.make_persistent("hecuba_test.wordsso")

        count, = config.session.execute('SELECT count(*) FROM hecuba_test.wordsso_words')[0]
        self.assertEqual(10, count)

        nopars2 = Test6StorageObj("hecuba_test.nonames")
        nopars2.test3[0] = '1', '2'
        result = config.session.execute("SELECT val0, val1 FROM hecuba_test.nonames_test3 WHERE key0 = 0")

        for row in result:
            rval0 = row.val0
            rval1 = row.val1

        self.assertEqual('1', rval0)
        self.assertEqual('2', rval1)

    def test_empty_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.wordsso_words")
        config.session.execute("DROP TABLE IF EXISTS my_app.wordsso")
        from app.words import Words
        so = Words()
        so.make_persistent("wordsso")
        so.ciao = "an attribute"
        so.another = 123
        config.batch_size = 1
        config.cache_activated = False
        for i in range(10):
            so.words[i] = str.join(',', map(lambda a: "ciao", range(i)))

        del so

        count, = config.session.execute('SELECT count(*) FROM my_app.wordsso_words')[0]
        self.assertEqual(10, count)
        so = Words()
        so.make_persistent("wordsso")
        so.delete_persistent()

        count, = config.session.execute('SELECT count(*) FROM my_app.wordsso_words')[0]
        self.assertEqual(0, count)

    def test_simple_stores_after_make_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.t2")
        so = Test2StorageObj()
        so.name = 'caio'
        so.age = 1000
        so.make_persistent("t2")
        count, = config.session.execute("SELECT COUNT(*) FROM my_app.t2")[0]
        self.assertEqual(count, 1)
        self.assertEqual(so.name, 'caio')
        self.assertEqual(so.age, 1000)

    def test_simple_attributes(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.t2")
        so = Test2StorageObj()
        so.make_persistent("t2")
        so.name = 'caio'
        so.age = 1000
        count, = config.session.execute("SELECT COUNT(*) FROM my_app.t2")[0]
        self.assertEqual(count, 1)
        self.assertEqual(so.name, 'caio')
        self.assertEqual(so.age, 1000)

    def test_modify_simple_attributes(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.t2")
        so = Test2StorageObj()
        so.make_persistent("t2")
        so.name = 'caio'
        so.age = 1000
        count, = config.session.execute("SELECT COUNT(*) FROM my_app.t2")[0]
        self.assertEqual(count, 1)
        self.assertEqual(so.name, 'caio')
        self.assertEqual(so.age, 1000)
        so.name = 'addio'
        so.age = 2000
        self.assertEqual(so.name, 'addio')
        self.assertEqual(so.age, 2000)

    def test_modify_simple_before_mkp_attributes(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.t2")
        so = Test2StorageObj()
        so.name = 'caio'
        so.age = 1000
        so.make_persistent("t2")
        count, = config.session.execute("SELECT COUNT(*) FROM my_app.t2")[0]
        self.assertEqual(count, 1)
        self.assertEqual(so.name, 'caio')
        self.assertEqual(so.age, 1000)
        so.name = 'addio'
        so.age = 2000
        self.assertEqual(so.name, 'addio')
        self.assertEqual(so.age, 2000)

    def test_parse_index_on(self):
        a = TestStorageIndexedArgsObj()
        self.assertEqual(a.test._indexed_args, ['x', 'y', 'z'])
        a.make_persistent('tparse.t1')
        from storage.api import getByID
        b = getByID(a.getID())
        self.assertEqual(b.test._indexed_args, ['x', 'y', 'z'])

    def test_nestedso_notpersistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.myso")

        my_nested_so = Test3StorageObj()

        my_nested_so.myso.name = 'Link'
        self.assertEquals('Link', my_nested_so.myso.name)
        my_nested_so.myso.age = '10'
        self.assertEquals('10', my_nested_so.myso.age)

        error = False
        try:
            config.session.execute('SELECT * FROM my_app.myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(True, error)

        my_nested_so.myso2.test[0] = 'position0'
        self.assertEquals('position0', my_nested_so.myso2.test[0])

        my_nested_so2 = Test4StorageObj()

        my_nested_so2.myotherso.name = 'Link'
        self.assertEquals('Link', my_nested_so2.myotherso.name)
        my_nested_so2.myotherso.age = '10'
        self.assertEquals('10', my_nested_so2.myotherso.age)

        error = False
        try:
            config.session.execute('SELECT * FROM my_app.myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(True, error)

        my_nested_so3 = Test4bStorageObj('mynested')
        my_nested_subso = my_nested_so3.myotherso

        my_other_nested = getByID(my_nested_subso.getID())
        my_other_nested.name = 'bla'
        my_other_nested.age = 5
        self.assertEqual(name, config.execution_name + '.' + r.name2)
        try:
            result = config.session.execute('SELECT * FROM my_app.mynested_myotherso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(False, error)
        for row in result:
            query_res = row
        self.assertEquals(5, query_res.age)
        self.assertEquals('bla', query_res.name)

    def test_nestedso_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.myso")

        my_nested_so = Test3StorageObj('mynewso')
        self.assertEquals(True, my_nested_so._is_persistent)
        self.assertEquals(True, my_nested_so.myso._is_persistent)
        self.assertEquals(True, my_nested_so.myso2._is_persistent)
        self.assertEquals(True, my_nested_so.myso2.test._is_persistent)

        my_nested_so.myso.name = 'Link'
        my_nested_so.myso.age = 10
        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.mynewso_myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(False, error)
        for row in result:
            query_res = row
        self.assertEquals(10, query_res.age)
        self.assertEquals('Link', query_res.name)

        my_nested_so.myso2.test[0] = 'position0'
        self.assertEquals('position0', my_nested_so.myso2.test[0])

        for value in my_nested_so.myso2.test.itervalues():
            self.assertEquals('position0', value)

        for key in my_nested_so.myso2.test.iterkeys():
            self.assertEquals(0, key)

        for value in my_nested_so.myso2.test.iteritems():
            self.assertEquals(2, len(value))
            self.assertEqual(0, value.key)
            self.assertEqual('position0', value.value)

    def test_nestedso_topersistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.myso")

        my_nested_so = Test3StorageObj()

        my_nested_so.myso.name = 'Link'
        self.assertEquals('Link', my_nested_so.myso.name)
        my_nested_so.myso.age = 10
        self.assertEquals(10, my_nested_so.myso.age)
        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(True, error)

        my_nested_so.make_persistent('mynewso')

        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.mynewso_myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(False, error)
        for row in result:
            query_res = row
        self.assertEquals(10, query_res.age)
        self.assertEquals('Link', query_res.name)

    def test_nestedso_sets_gets(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.myso")
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso_myso")

        my_nested_so = Test3StorageObj()

        my_nested_so.myso.name = 'Link'
        self.assertEquals('Link', my_nested_so.myso.name)
        my_nested_so.myso.age = 10
        self.assertEquals(10, my_nested_so.myso.age)
        my_nested_so.myso.weight = 70
        self.assertEquals(70, my_nested_so.myso.weight)
        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.mynewso_myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(True, error)

        my_nested_so.make_persistent('mynewso')

        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.mynewso_myso')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(False, error)
        for row in result:
            query_res = row
        self.assertEquals(10, query_res.age)
        self.assertEquals('Link', query_res.name)
        error = False
        try:
            _ = query_res.weight
        except:
            error = True
        self.assertEquals(True, error)
        my_nested_so.myso.weight = 50
        self.assertEquals(50, my_nested_so.myso.weight)
        result = config.session.execute('SELECT * FROM my_app.mynewso_myso')
        for row in result:
            query_res = row
        error = False
        try:
            _ = query_res.weight
        except:
            error = True
        self.assertEquals(True, error)

    def test_nestedso_sets_gets_complex(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso_myso2")
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso_myso2_test")

        my_nested_so = Test3StorageObj()

        error = False
        try:
            _ = config.session.execute('SELECT * FROM my_app.mynewso_myso2')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(True, error)

        my_nested_so.make_persistent('mynewso')

        error = False
        try:
            _ = config.session.execute('SELECT * FROM my_app.mynewso_myso2')
        except cassandra.InvalidRequest:
            error = True
        self.assertEquals(False, error)

        for i in range(0, 100):
            my_nested_so.myso2.test[i] = 'position' + str(i)
        time.sleep(5)
        count, = config.session.execute("SELECT COUNT(*) FROM my_app.mynewso_myso2_test")[0]
        self.assertEquals(100, count)

    def test_nestedso_deletepersistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.myso")

        my_nested_so = Test3StorageObj('mynewso')

        self.assertEquals(True, my_nested_so._is_persistent)
        my_nested_so.myso.name = 'Link'
        self.assertEquals('Link', my_nested_so.myso.name)
        my_nested_so.myso.age = 10
        self.assertEquals(10, my_nested_so.myso.age)

        my_nested_so.delete_persistent()

        self.assertEquals(False, my_nested_so._is_persistent)
        entries = 0
        try:
            _ = config.session.execute('SELECT * FROM my_app.mynewso_myso')
        except cassandra.InvalidRequest:
            entries += 1
        self.assertEquals(0, entries)

    def test_nestedso_dictofsos(self)
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso_test2")

        my_nested_so = Test5StorageObj('mynewso')

        self.assertEquals(True, my_nested_so._is_persistent)
        self.assertEquals(True, my_nested_so.test2._is_persistent)
        self.assertEquals(True, my_nested_so.test2.myso._is_persistent)

        my_nested_so.test2.myso.name = 'Link'
        self.assertEquals('Link', my_nested_so.test2.myso.name)
        my_nested_so.test2.myso.age = 10
        self.assertEquals(10, my_nested_so.test2.myso.age)

    def test_nestedso_retrievedata(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso")
        config.session.execute("DROP TABLE IF EXISTS my_app.mynewso_test2")

        my_nested_so = Test5StorageObj('mynewso')

        self.assertEquals(True, my_nested_so._is_persistent)
        self.assertEquals(True, my_nested_so.test2._is_persistent)
        self.assertEquals(True, my_nested_so.test2.myso._is_persistent)

        my_nested_so.test2.myso.name = 'Link'
        self.assertEquals('Link', my_nested_so.test2.myso.name)
        my_nested_so.test2.myso.age = 10
        self.assertEquals(10, my_nested_so.test2.myso.age)

        del my_nested_so

        my_nested_so2 = Test5StorageObj('mynewso')

        self.assertEquals('Link', my_nested_so2.test2.myso.name)
        self.assertEquals(10, my_nested_so2.test2.myso.age)


if __name__ == '__main__':
    unittest.main()
