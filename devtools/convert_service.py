#!/usr/bin/python

import ast
import codecs
import json
import pprint
import sys
import yaml


def normalize_input(s):
    s = s.replace("u'", "'")
    s = s.replace("'", "\"")

    return s

def main(args):
    if len(args) != 2:
        sys.exit(1)

    pp = pprint.PrettyPrinter(indent="2")

    f = codecs.open(args[1], encoding='utf-8')
    s = f.readline()

    s = normalize_input(s)

    try:
        d = yaml.load(s)
    except Exception as err:
        print "Failed to load as yaml: "
        print err.message

    print json.dumps(d, indent=4)

if __name__ == '__main__':
    main(sys.argv)

