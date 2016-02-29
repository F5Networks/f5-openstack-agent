# Copyright 2016 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os

from setuptools import find_packages
from setuptools import setup

if 'PROJECT_DIR' in os.environ:
    project_dir = os.environ['PROJECT_DIR']
else:
    project_dir = os.path.curdir


def version():
    if 'VERSION' in os.environ:
        version = os.environ['VERSION']
    elif os.path.isfile('VERSION'):
        with open('VERSION') as f:
            version = f.read()
    else:
        version = 'Unknown'

    return version


def release():
    if 'RELEASE' in os.environ:
        release = os.environ['RELEASE']
    elif os.path.isfile('RELEASE'):
        with open('RELEASE') as f:
            release = f.read().strip()
    else:
        release = 'Unknown'

    return release


def readme():
    with open('README.md') as f:
        return f.read()

setup(name='f5-openstack-agent',

      description='F5 Networks Agent for OpenStack services',
      long_description=readme(),
      version=version(),
      author='f5-openstack-agent',
      author_email='f5-openstack-agent@f5.com',
      url='https://github.com/F5Networks/f5-openstack-agent',

      # Runtime dependencies.
      install_requires=[],

      packages=find_packages(exclude=["*.test", "*.test.*", "test*", "test"]),

      classifiers=['Development Status :: 2 - Pre-Alpha',
                   'License :: OSI Approved :: Apache Software License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Intended Audience :: System Administrators']
      )
