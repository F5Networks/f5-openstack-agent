import json
from pprint import pprint as pp

pairs_esd = json.load(open("/home/stack/f5-openstack-agent/test/functional/testdata/esds/esd_pairs.json"))


for key in pairs_esd.keys():
    test_name = key.replace("f5_ESD", "test_esd")
    outstring = "def %s(ESD_Pairs_Experiment):\n    '''Pair test'''\n" % test_name
    print(outstring)
