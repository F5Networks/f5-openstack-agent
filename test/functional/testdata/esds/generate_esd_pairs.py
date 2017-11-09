import json
import os
from pprint import pprint as pp

DIRNAME = os.path.dirname(os.path.abspath(__file__))

def load_full_demo_esd():
    """Return an esd dict containing state specced in demo.json."""
    esd_file = os.path.join(DIRNAME, 'demo.json')
    several_esds = json.load(open(esd_file))
    return several_esds['f5_ESD_full_8_tag_set']

eight_tag_esd = load_full_demo_esd()

print(eight_tag_esd.keys())

def create_demo_subset_esd(*args):
    subset_esd = {}
    for arg in args:
        subset_esd[arg] = eight_tag_esd[arg]
    return subset_esd

def create_pairs_esd(tags):
    pairs_esd = {}
    for index, tag in enumerate(tags):
        for ntag in tags[index+1:]:
            fullname = "f5_ESD_" + tag + "_" + ntag
            pairs_esd[fullname] = {tag: eight_tag_esd[tag],
                                   ntag: eight_tag_esd[ntag]}
    return pairs_esd

pairs_esd = create_pairs_esd(eight_tag_esd.keys())
pp(pairs_esd)
print(len(pairs_esd))
json.dump(pairs_esd, open(DIRNAME+"/esd_pairs.json", 'w'), indent=4)
