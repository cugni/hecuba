import unittest

from mock import Mock

from hecuba.IStorage import IStorage
from app.words import Words
from hecuba import config, Config
from hecuba import hdict
from hecuba import StorageDict


class TestHdict(StorageDict):
    '''
        @TypeSpec dict<<position:int>,text:str>
    '''
    pass


class HdictTest(unittest.TestCase):
    def setUp(self):
        Config.reset(mock_cassandra=True)

    # TEST POSSIBLE WRONG INPUTS

    ######################################################################

    # SAME AS STORAGEOBJ

    ######################################################################

    # IMPLEMENTATION

    # PARSE X DATA

    def test_parse_2(self):
        comment = '''
            @TypeSpec particles dict<<partid:int>,x:int,y:int,z:int>
            '''
        pd = StorageDict(None,
                         [('pk1', 'int')],
                         [('val1', 'text')])
        p = pd._parse_comments(comment)
        should_be = {'particles': {
            'columns': [('x', 'int'), ('y', 'int'), ('z', 'int')],
            'primary_keys': [('partid', 'int')],
            'type': 'StorageDict'
        }}
        self.assertEquals(p, should_be)
