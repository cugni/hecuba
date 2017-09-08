import unittest

from hecuba import config
from hecuba.hdict import StorageDict
from app.words import Words
import uuid
import time


class MyStorageDict(StorageDict):
    '''
    @TypeSpec <<position:int>,val:int>
    '''
    pass


class MyStorageDict2(StorageDict):
    '''
    @TypeSpec <<position:int, position2:str>,val:int>
    '''
    pass


class StorageDictTest(unittest.TestCase):
    def test_init_empty(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab1")
        tablename = "ksp.tab1"
        tokens = [(1l, 2l), (2l, 3l), (3l, 4l)]
        nopars = StorageDict(tablename,
                             [('position', 'int')],
                             [('value', 'str')],
                             tokens)
        self.assertEqual("tab1", nopars._table)
        self.assertEqual("ksp", nopars._ksp)

        res = config.session.execute(
            'SELECT storage_id, primary_keys, columns, class_name, name, tokens, istorage_props,indexed_on ' +
            'FROM hecuba.istorage WHERE storage_id = %s', [nopars._storage_id])[0]

        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, tablename), nopars._storage_id)
        self.assertEqual(nopars.__class__.__module__, 'hecuba.hdict')
        self.assertEqual(nopars.__class__.__name__, 'StorageDict')

        rebuild = StorageDict.build_remotely(res)
        self.assertEqual('tab1', rebuild._table)
        self.assertEqual("ksp", rebuild._ksp)
        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, tablename), rebuild._storage_id)

        self.assertEqual(nopars._is_persistent, rebuild._is_persistent)

    def test_init_empty_def_keyspace(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab1")
        tablename = "tab1"
        tokens = [(1l, 2l), (2l, 3l), (3l, 4l)]
        nopars = StorageDict(tablename,
                             [('position', 'int')],
                             [('value', 'int')],
                             tokens)
        self.assertEqual("tab1", nopars._table)
        self.assertEqual(config.execution_name, nopars._ksp)

        res = config.session.execute(
            'SELECT storage_id, primary_keys, columns, class_name, name, tokens, istorage_props,indexed_on ' +
            'FROM hecuba.istorage WHERE storage_id = %s', [nopars._storage_id])[0]

        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.' + tablename), nopars._storage_id)
        self.assertEqual(nopars.__class__.__module__, 'hecuba.hdict')
        self.assertEqual(nopars.__class__.__name__, 'StorageDict')

        rebuild = StorageDict.build_remotely(res)
        self.assertEqual('tab1', rebuild._table)
        self.assertEqual(config.execution_name, rebuild._ksp)
        self.assertEqual(uuid.uuid3(uuid.NAMESPACE_DNS, config.execution_name + '.' + tablename), rebuild._storage_id)

        self.assertEqual(nopars._is_persistent, rebuild._is_persistent)

    def test_simple_insertions(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab10")
        tablename = "tab10"
        tokens = [(1l, 2l), (2l, 3l), (3l, 4l)]
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')],
                         tokens)

        for i in range(100):
            pd[i] = 'ciao' + str(i)
        del pd
        count, = config.session.execute('SELECT count(*) FROM my_app.tab10')[0]
        self.assertEqual(count, 100)

    def test_dict_print(self):
        tablename = "tab10"
        config.session.execute("DROP TABLE IF EXISTS my_app." + tablename)
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])

        self.assertEquals(pd.__repr__(), "")

        pd[0] = 'a'
        self.assertEquals(pd.__repr__(), "{0: 'a'}")

        pd[1] = 'b'
        self.assertEquals(pd.__repr__(), "{0: 'a', 1: 'b'}")

        for i in range(1100):
            pd[i] = str(i)
        self.assertEquals(pd.__repr__().count(':'), 1000)

    def test_get_strs(self):
        tablename = "tab10"
        config.session.execute("DROP TABLE IF EXISTS my_app." + tablename)
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        pd[0] = 'str1'
        self.assertEquals(pd[0], 'str1')
        '''
        config.session.execute("DROP TABLE IF EXISTS my_app." + tablename)
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'list<str>')])
        pd[0] = ['str1', 'str2']
        self.assertEquals(pd[0], ['str1', 'str2'])

        config.session.execute("DROP TABLE IF EXISTS my_app." + tablename)
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'tuple<str,str>')])
        pd[0] = 'str1', 'str2'
        self.assertEquals(pd[0], 'str1', 'str2')
        '''

    def test_make_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.t_make_words")
        nopars = Words()
        self.assertFalse(nopars._is_persistent)
        nopars.ciao = 1
        nopars.ciao2 = "1"
        nopars.ciao3 = [1, 2, 3]
        nopars.ciao4 = (1, 2, 3)
        for i in range(10):
            nopars.words[i] = 'ciao' + str(i)

        count, = config.session.execute(
            "SELECT count(*) FROM system_schema.tables WHERE keyspace_name = 'my_app' and table_name = 't_make_words'")[0]
        self.assertEqual(0, count)

        nopars.make_persistent("t_make")

        del nopars
        count, = config.session.execute('SELECT count(*) FROM my_app.t_make_words')[0]
        self.assertEqual(10, count)

    def test_paranoid_setitem_nonpersistent(self):
        config.hecuba_type_checking = True
        pd = StorageDict(None,
                         [('position', 'int')],
                         [('value', 'str')])
        pd[0] = 'bla'
        self.assertEquals(pd[0], 'bla')

        def set_wrong_val_1():
            pd[0] = 1
        self.assertRaises(ValueError, set_wrong_val_1)

        def set_wrong_val_2():
            pd['bla'] = 'bla'
        self.assertRaises(KeyError, set_wrong_val_2)
        config.hecuba_type_checking = False

    def test_paranoid_setitem_multiple_nonpersistent(self):
        config.hecuba_type_checking = True
        pd = StorageDict(None,
                         [('position1', 'int'), ('position2', 'str')],
                         [('value1', 'str'), ('value2', 'int')])
        pd[0, 'pos1'] = 'bla', 1
        self.assertEquals(pd[0, 'pos1'], ('bla', 1))

        def set_wrong_val_1():
            pd[0, 'pos1'] = 1, 'bla'
        self.assertRaises(ValueError, set_wrong_val_1)

        def set_wrong_val_2():
            pd['pos1', 0] = 'bla', 1
        self.assertRaises(KeyError, set_wrong_val_2)
        config.hecuba_type_checking = False

    def test_paranoid_setitem_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a1")
        config.hecuba_type_checking = True
        pd = StorageDict("tab_a1",
                         [('position', 'int')],
                         [('value', 'str')])
        pd[0] = 'bla'
        result = config.session.execute('SELECT value FROM my_app.tab_a1 WHERE position = 0')
        for row in result:
            self.assertEquals(row.value, 'bla')

        def set_wrong_val_test():
            pd[0] = 1
        self.assertRaises(ValueError, set_wrong_val_test)
        config.hecuba_type_checking = False

    def test_paranoid_setitem_multiple_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a2")
        config.hecuba_type_checking = True
        pd = StorageDict("tab_a2",
                         [('position1', 'int'), ('position2', 'str')],
                         [('value1', 'str'), ('value2', 'int')])
        pd[0, 'pos1'] = 'bla', 1
        for result in pd.itervalues():
            self.assertEquals(result.value1, 'bla')
            self.assertEquals(result.value2, 1)

        def set_wrong_val():
            pd[0, 'pos1'] = 'bla', 'bla1'
        self.assertRaises(ValueError, set_wrong_val)

        def set_wrong_key():
            pd['bla', 'pos1'] = 'bla', 1
        self.assertRaises(KeyError, set_wrong_key)
        config.hecuba_type_checking = False

    def test_paranoid_setitemdouble_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a3")
        config.hecuba_type_checking = True
        pd = StorageDict("tab_a3",
                         [('position', 'int')],
                         [('value', 'double')])
        pd[0] = 2.0
        result = config.session.execute('SELECT value FROM my_app.tab_a3 WHERE position = 0')
        for row in result:
            self.assertEquals(row.value, 2.0)

        def set_wrong_val_test():
            pd[0] = 1
        self.assertRaises(ValueError, set_wrong_val_test)
        config.hecuba_type_checking = False

    def test_paranoid_setitemdouble_multiple_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a4")
        config.hecuba_type_checking = True
        pd = StorageDict("tab_a4",
                         [('position1', 'int'), ('position2', 'str')],
                         [('value1', 'str'), ('value2', 'double')])
        pd[0, 'pos1'] = ['bla', 1.0]
        time.sleep(2)
        self.assertEquals(pd[0, 'pos1'], ('bla', 1.0))
        config.hecuba_type_checking = False

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

        so = Words("wordsso")
        so.delete_persistent()
        so.words.delete_persistent()

        count, = config.session.execute('SELECT count(*) FROM my_app.wordsso_words')[0]
        self.assertEqual(0, count)

    def test_simple_iteritems_test(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a1")

        pd = StorageDict("tab_a1",
                         [('position', 'int')],
                         [('value', 'str')])

        what_should_be = {}
        for i in range(100):
            pd[i] = 'ciao' + str(i)
            what_should_be[i] = 'ciao' + str(i)
        del pd
        count, = config.session.execute('SELECT count(*) FROM my_app.tab_a1')[0]
        self.assertEqual(count, 100)
        pd = StorageDict("tab_a1",
                         [('position', 'int')],
                         [('value', 'str')])
        count = 0
        res = {}
        for key, val in pd.iteritems():
            res[key] = val
            count += 1
        self.assertEqual(count, 100)
        self.assertEqual(what_should_be, res)

    def test_simple_itervalues_test(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a2")
        tablename = "tab_a2"
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])

        what_should_be = set()
        for i in range(100):
            pd[i] = 'ciao' + str(i)
            what_should_be.add('ciao' + str(i))
        del pd
        count, = config.session.execute('SELECT count(*) FROM my_app.tab_a2')[0]

        self.assertEqual(count, 100)

        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        count = 0
        res = set()
        for val in pd.itervalues():
            res.add(val)
            count += 1
        self.assertEqual(count, 100)
        self.assertEqual(what_should_be, res)

    def test_simple_iterkeys_test(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a3")
        tablename = "tab_a3"
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])

        what_should_be = set()
        for i in range(100):
            pd[i] = 'ciao' + str(i)
            what_should_be.add(i)
        del pd
        count, = config.session.execute('SELECT count(*) FROM my_app.tab_a3')[0]
        self.assertEqual(count, 100)
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        count = 0
        res = set()
        for val in pd.iterkeys():
            res.add(val)
            count += 1
        self.assertEqual(count, 100)
        self.assertEqual(what_should_be, res)

    def test_simple_contains(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a4")
        tablename = "tab_a4"
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])

        for i in range(100):
            pd[i] = 'ciao' + str(i)
        del pd
        count, = config.session.execute('SELECT count(*) FROM my_app.tab_a4')[0]
        self.assertEqual(count, 100)

        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        for i in range(100):
            self.assertTrue(i in pd)

    def test_deleteitem_nonpersistent(self):
        pd = StorageDict(None,
                         [('position', 'int')],
                         [('value', 'str')])
        pd[0] = 'to_delete'
        del pd[0]

        def del_val():
            val = pd[0]
        self.assertRaises(KeyError, del_val)

        pd = StorageDict(None,
                         [('position', 'str')],
                         [('value', 'int')])
        pd['pos0'] = 0
        del pd['pos0']

        def del_val():
            val = pd['pos0']
        self.assertRaises(KeyError, del_val)

    def test_deleteitem_persistent(self):
        tablename = "tab_a5"
        config.session.execute("DROP TABLE IF EXISTS my_app." + tablename)
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        pd[0] = 'to_delete'
        del pd[0]

        def del_val():
            val = pd[0]
        self.assertRaises(KeyError, del_val)

        tablename = "tab_a6"
        config.session.execute("DROP TABLE IF EXISTS my_app." + tablename)
        pd = StorageDict(tablename,
                         [('position', 'str')],
                         [('value', 'int')])
        pd['pos1'] = 0
        del pd['pos1']

        def del_val():
            val = pd['pos1']
        self.assertRaises(KeyError, del_val)

    def test_composed_iteritems_test(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab12")
        tablename = "tab12"
        pd = StorageDict(tablename,
                         [('pid', 'int'), ('time', 'int')],
                         [('value', 'str'), ('x', 'double'), ('y', 'double'), ('z', 'double')])

        what_should_be = {}
        for i in range(100):
            pd[i, i + 100] = ('ciao' + str(i), i * 0.1, i * 0.2, i * 0.3)
            what_should_be[i, i + 100] = ('ciao' + str(i), i * 0.1, i * 0.2, i * 0.3)

        del pd

        count, = config.session.execute('SELECT count(*) FROM my_app.tab12')[0]
        self.assertEqual(count, 100)
        pd = StorageDict(tablename,
                         [('pid', 'int'), ('time', 'int')],
                         [('value', 'str'), ('x', 'double'), ('y', 'double'), ('z', 'double')])
        count = 0
        res = {}
        for key, val in pd.iteritems():
            res[key] = val
            count += 1
        self.assertEqual(count, 100)
        delta = 0.000001
        for i in range(100):
            a = what_should_be[i, i + 100]
            b = res[i, i + 100]
            self.assertEqual(a[0], b.value)
            self.assertAlmostEquals(a[1], b.x, delta=delta)
            self.assertAlmostEquals(a[2], b.y, delta=delta)
            self.assertAlmostEquals(a[3], b.z, delta=delta)

    def test_composed_key_return_list_iteritems_test(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab13")
        tablename = "tab13"
        pd = StorageDict(tablename,
                         [('pid', 'int'), ('time', 'double')],
                         [('value', 'str'), ('x', 'double'), ('y', 'double'), ('z', 'double')])

        what_should_be = {}
        for i in range(100):
            pd[i, i + 100.0] = ('ciao' + str(i), i * 0.1, i * 0.2, i * 0.3)
            what_should_be[i, i + 100.0] = ('ciao' + str(i), i * 0.1, i * 0.2, i * 0.3)

        del pd

        count, = config.session.execute('SELECT count(*) FROM my_app.tab13')[0]
        self.assertEqual(count, 100)
        pd = StorageDict(tablename,
                         [('pid', 'int')],
                         [('time', 'double'), ('value', 'str'), ('x', 'double'), ('y', 'double'), ('z', 'double')])
        count = 0
        res = {}
        for key, val in pd.iteritems():
            self.assertTrue(isinstance(key, int))
            self.assertTrue(isinstance(val[0], float))
            res[key] = val
            count += 1
        self.assertEqual(count, 100)
        # casting to avoid 1.0000001 float python problem
        data = set([(key, int(val.time), val.value, int(val.x), int(val.y), int(val.z)) for key, val in pd.iteritems()])
        data2 = set([(key[0], int(key[1]), val[0], int(val[1]), int(val[2]), int(val[3])) for key, val in what_should_be.iteritems()])
        self.assertEqual(data, data2)

    def test_storagedict_newinterface_localmemory(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.my_dict")

        my_dict = MyStorageDict()
        my_dict[0] = 1
        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.my_dict')[0]
        except Exception as e:
            error = True
        self.assertEquals(True, error)

    def test_storagedict_newinterface_memorytopersistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.my_dict")

        my_dict = MyStorageDict()
        my_dict[0] = 1
        error = False
        try:
            result = config.session.execute('SELECT * FROM my_app.my_dict')[0]
        except Exception as e:
            error = True
        self.assertEquals(True, error)

        my_dict.make_persistent('my_dict')
        count, = config.session.execute('SELECT count(*) FROM my_app.my_dict')[0]
        self.assertEquals(1, count)

    def test_storagedict_newinterface_persistent(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.my_dict")

        my_dict = MyStorageDict()
        my_dict[0] = 1
        my_dict.make_persistent('my_dict')
        time.sleep(1)
        count, = config.session.execute('SELECT count(*) FROM my_app.my_dict')[0]
        self.assertEquals(1, count)

        my_dict[1] = 2
        time.sleep(1)
        count, = config.session.execute('SELECT count(*) FROM my_app.my_dict')[0]
        self.assertEquals(2, count)

        my_dict2 = MyStorageDict('my_dict')
        self.assertEquals(1, my_dict2[0])
        self.assertEquals(2, my_dict2[1])

    def test_update(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a4")
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a5")
        tablename = "tab_a4"
        pd = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        pd[0] = 'prev_a'
        pd[1] = 'prev_b'
        self.assertEquals(pd[0], 'prev_a')
        self.assertEquals(pd[1], 'prev_b')
        pd.update({0: 'a', 1: 'b'})
        time.sleep(1)
        self.assertEquals(pd[0], 'a')
        self.assertEquals(pd[1], 'b')
        pd.update({2: 'c', 3: 'd'})
        time.sleep(1)
        self.assertEquals(pd[0], 'a')
        self.assertEquals(pd[1], 'b')
        self.assertEquals(pd[2], 'c')
        self.assertEquals(pd[3], 'd')
        tablename = "tab_a5"
        pd2 = StorageDict(tablename,
                         [('position', 'int')],
                         [('value', 'str')])
        pd2[0] = 'final_a'
        pd2[4] = 'final_4'
        pd.update(pd2)
        time.sleep(1)
        self.assertEquals(pd[0], 'final_a')
        self.assertEquals(pd[4], 'final_4')

    def test_update_kwargs(self):
        config.session.execute("DROP TABLE IF EXISTS my_app.tab_a6")
        tablename = "tab_a6"
        pd = StorageDict(tablename,
                         [('position', 'str')],
                         [('value', 'str')])
        pd['val1'] = 'old_a'
        pd['val2'] = 'old_b'
        time.sleep(2)
        self.assertEquals(pd['val1'], 'old_a')
        self.assertEquals(pd['val2'], 'old_b')
        pd.update(val1='new_a', val2='new_b')
        time.sleep(2)
        self.assertEquals(pd['val1'], 'new_a')
        self.assertEquals(pd['val2'], 'new_b')


if __name__ == '__main__':
    unittest.main()
