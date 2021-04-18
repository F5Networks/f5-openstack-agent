# -*- coding: utf-8 -*-

import json
import os
import shutil


class FilePublisher(object):

    def __init__(self, dirctory):
        self.path = "/tmp/check_" + str(dirctory)
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        os.mkdir(self.path)

    def write_json(self, filename, context):
        file_path = self.path + "/" + filename
        with open(file_path, 'a') as f:
            json.dump(context, f, indent=2, sort_keys=True)
