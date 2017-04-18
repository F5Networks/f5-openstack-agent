#! /usr/bin/env python
import sys
import json

indata = json.load(open(sys.argv[1], 'r'))

open(sys.argv[1], 'w').write(json.dumps(indata, indent=4, sort_keys=True))
