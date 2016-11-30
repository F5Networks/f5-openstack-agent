.. raw:: html

   <!--
   Copyright 2015-2016 F5 Networks Inc.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
   -->

f5-openstack-agent
##################

|Build Status| |slack badge| |coveralls badge|

Introduction
************

The F5® agent translates from 'OpenStack' to 'F5®'. It uses the `f5-sdk <http://f5-sdk.readthedocs.io>`_ to translate OpenStack messaging calls -- such as those from the Neutron RPC messaging queue -- into iControl® REST calls to F5® technologies, such as BIG-IP®.

Documentation
*************

Documentation is published on Read the Docs, at http://f5-openstack-agent.readthedocs.io.

Compatibility
*************

The F5® OpenStack agent is compatible with OpenStack releases from Liberty forward. If you are using Kilo or earlier, you'll need the `LBaaSv1 plugin <http://f5-openstack-lbaasv1.readthedocs.io>`_.

See the `F5® OpenStack Releases and Support Matrix <http://f5-openstack-docs.readthedocs.org/en/latest/releases_and_versioning.html>`_ for more information.

Installation
************

Please see the `documentation <http://f5-openstack-agent.readthedocs.io>`_ for installation instructions.

For Developers
**************

Filing Issues
=============

If you find an issue, we would love to hear about it. Please open a new `issue <https://github.com/F5Networks/f5-openstack-agent/issues>`_ aissue for each bug you'd like to report or feature you'd like to request. Please be specific, and include as much information about your environment and the issue as possible.

Contributing
************
See `Contributing <CONTRIBUTING.md>`_.

Test
****
Before you open a pull request, your code must have passing
`pytest <http://pytest.org>`__ unit tests. In addition, you should
include a set of functional tests written to use a real BIG-IP® device
for testing. Information on how to run our set of tests is included
below.

Style Checks
============

We use the hacking module for our style checks.

::
    $ pip install hacking
    $ flake8 ./f5_openstack_agent

Unit Tests
==========

We use tox to run our pytest unit tests. To run the unit tests use the tox
environment `unit`.

::
    $ pip install tox
    $ tox -e unit

Functional Tests
=================

Functional tests can be run without a full OpenStack deployment, but do require
access to a BIG-IP device or VE instance.

1. Create a symbol's file that describes the environment that you are running
   your test in by copying and editing the `symbols.json.example <test/functional/symbols.json.example>`_
   file to have the values that are correct for your BIG-IP.

2. Run the functional tests by supplying the symbol file that you just created
   which includes the information relative to your environment using the
   example file. The example below runs the disconnected services neutronless
   functional test cases.

::

    $ tox -e functest -- \
      --symbols ~/path/to/symbols/symbols.json \
      ./test/functional/neutronless/disconnected_service

Troubleshooting
===============

When the f5-openstack-agent is installed, the *debug_bundler.py* script will be installed to */usr/bin/f5/*. This script can be run from the command line directly. It will search in the specified directories to bundle log files and configuration files for use in debugging an issue with the f5-openstack-agent. In addition to the above files, it also dumps a complete listing of the ``pip lists`` output.

**WARNING**

The files added to this bundle may contain VERY SENSITIVE INFORMATION such as encryption keys, passwords, and usernames. Do not upload this bundle, or any information within, to a public forum unless you have scrubbed sensitive information thoroughly. When in doubt, don't upload it at all.

Below you can see the basic usage, using the default command-line arguments:

::

    $ python /usr/bin/f5/debug_bundler.py /home/myuser/debug_bundle_output/

A tarred, compressed, file will be created in the directory specified. It will contain all logs and configuration files the script found. Note that the script offers a best-effort search of the directories given, and if it cannot find the log files it is looking for in those directories, it will print a message and continue running.

The default log location is set to `/var/log/neutron` and the default configuration file location is in `/etc/neutron`. These locations can be overriden via the command-line invocation shown below:

::

    $ python /usr/bin/f5/debug_bundler.py --log-dir=/var/log/mylogs --config-dir /etc/myconfigs/ ~/

If any issue is found with the debug_bundler script, please file an issue on GitHub.

Copyright
*********

Copyright 2015-2016 F5 Networks Inc.

Support
*******

See `Support <SUPPORT.md>`_.

License
*******

Apache V2.0
===========

Licensed under the Apache License, Version 2.0 (the "License"); you may
not use this file except in compliance with the License. You may obtain
a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Contributor License Agreement
=============================

Individuals or business entities who contribute to this project must have completed and submitted the `F5® Contributor License Agreement <http://f5-openstack-docs.readthedocs.org/en/latest/cla_landing.html#cla-landing>`_ to Openstack\_CLA@f5.com prior to their code submission being included in this project.


.. |Build Status| image:: https://travis-ci.org/F5Networks/f5-openstack-agent.svg?branch=liberty
   :target: https://travis-ci.org/F5Networks/f5-openstack-agent?branch=liberty

.. |slack badge| image:: https://f5-openstack-slack.herokuapp.com/badge.svg
    :target: https://f5-openstack-slack.herokuapp.com/
    :alt: Slack

.. |coveralls badge| image:: https://coveralls.io/repos/github/F5Networks/f5-openstack-agent/badge.svg?branch=liberty
    :target: https://coveralls.io/github/F5Networks/f5-openstack-agent?branch=liberty
    :alt: Coveralls
