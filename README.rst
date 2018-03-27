.. raw:: html

   <!--
   Copyright (c) 2015-2018, F5 Networks, Inc.

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

F5 Agent for OpenStack Neutron
==============================

|Build Status| |slack badge| |coveralls badge|

.. image:: https://coveralls.io/repos/github/F5Networks/f5-openstack-agent/badge.svg?branch=newton
:target: https://coveralls.io/github/F5Networks/f5-openstack-agent?branch=newton
         
Introduction
------------

The F5 Agent for OpenStack Neutron is an OpenStack `Neutron plugin agent <https://docs.openstack.org/admin-guide/networking-arch.html#overview>`_. It works in conjunction with the `F5 driver for OpenStack LBaaSv2 <http://clouddocs.f5.com/products/openstack/lbaasv2-driver/latest/index.html>`_ to manage F5 BIG-IP `Local Traffic Manager <https://f5.com/products/big-ip/local-traffic-manager-ltm>`_ (LTM) services via the OpenStack Neutron API.

Documentation
-------------

Documentation is published on `clouddocs.f5.com <http://clouddocs.f5.com/products/openstack/agent/latest>`_.

Compatibility
-------------

The F5 Agent for OpenStack Neutron is compatible with OpenStack releases from Liberty forward.

See the `F5 OpenStack Releases and Support Matrix <http://clouddocs.f5.com/cloud/openstack/latest/support/releases_and_versioning.html>`_ for more information.

Installing the F5 Agent
-----------------------

Please see the `product documentation <http://clouddocs.f5.com/products/openstack/agent/latest/#installation>`_.


Using the Built-in Debugger
---------------------------

Use the built-in debugger -- ``debug_bundler.py`` -- to package information about your environment for debugging purposes.

When the you install ``f5-openstack-agent``, the ``debug_bundler.py`` script installs itself in ``/usr/bin/f5/``.
When you run the debugger, it searches for log and config files and dumps a complete listing of the ``pip lists`` output.
The debugger bundles everything it finds into a tarfile that you can provide to F5's support representatives to assist them in identifying the cause of your issue.

-------------

**WARNING**

The files added to the debug bundle may contain **VERY SENSITIVE INFORMATION** such as **encryption keys**, **passwords**, and **usernames**.
Do not upload this bundle, or any information within, to a public forum unless you have thoroughly scrubbed sensitive information.
When in doubt, don't upload it at all.

-------------


Basic usage with the default command-line arguments
```````````````````````````````````````````````````

The command below creates a .tar file in the specified directory (in this example, `/home/myuser/debug_bundle_output/`) containing all logs and configuration files the script found.
The script offers a best-effort search of the specified directories.
If it cannot find the log files it is looking for in those directories, it prints an error message and continues to run.


::

  $ python /usr/bin/f5/debug_bundler.py /home/myuser/debug_bundle_output/



Override log/config file locations
``````````````````````````````````

The default log location is `/var/log/neutron`.
The default configuration file location is `/etc/neutron`.

To override the log and/or config file locations, use the command-line arguments shown below: ::

  $ python /usr/bin/f5/debug_bundler.py --log-dir=/var/log/mylogs --config-dir /etc/myconfigs/ ~/


Issues
``````

If you find any issues with the debug_bundler, please `file an issue <#filing-issues>`_.


For Developers
--------------

Filing Issues
`````````````

If you find an issue, we would love to hear about it.
Please file an `issue <https://github.com/F5Networks/f5-openstack-agent/issues>`_ in this repository.
Use the issue template to tell us as much as you can about what you found, how you found it, your environment, etc.
Admins will triage your issue and assign it for a fix based on the priority level assigned.
We also welcome you to file issues for feature requests.

Contributing
````````````

See `Contributing <CONTRIBUTING.md>`_.

Testing
```````

Before you open a pull request, your code must have passing `pytest <http://pytest.org>`__ unit tests.
In addition, you should include a set of functional tests written to use an actual BIG-IP device for testing.
Information on how to run our test set is included below.

Style Checks
~~~~~~~~~~~~

We use the ``hacking`` module for our style checks.

::

  $ pip install tox
  $ tox -e style

Unit Tests
~~~~~~~~~~

We use ``tox`` to run our ``pytest`` unit tests.

To run the unit tests, use the ``tox`` ``unit`` environment.

::

  $ pip install tox
  $ tox -e unit

Functional Tests
~~~~~~~~~~~~~~~~

You can run functional tests without a full OpenStack deployment.
They do require access to a BIG-IP device or BIG-IP Virtual Edition (VE) instance.

#. Copy and edit the `symbols.json.example <test/functional/symbols.json.example>`_ with the correct values for your BIG-IP device.

#. Run ``tox -e functest`` with the ``--symbols`` flag pointing to your updates symbols.json file.

   For example, the command below calls the symbols file and runs the ``neutronless/disconnected_service`` functional test cases.
   The ``tox`` target changes to the ``[test/functional](test/functional)`` directory before the tests run.

::

  $ tox -e functest -- \
    --symbols ~/path/to/symbols/symbols.json \
    neutronless/disconnected_service



Copyright
---------

Copyright (c) 2015-2018, F5 Networks, Inc.

Support
-------

See `Support <SUPPORT.md>`_.

License
-------

Apache V2.0
```````````

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
-----------------------------

Individuals or business entities who contribute to this project must complete and submit the `F5 Contributor License Agreement <http://clouddocs.f5.com/cloud/openstack/v1/support/cla_landing.html>`_ to Openstack\_CLA@f5.com **before** their code submission can be added to this project.


.. |Build Status| image:: https://travis-ci.org/F5Networks/f5-openstack-agent.svg?branch=newton
   :target: https://travis-ci.org/F5Networks/f5-openstack-agent?branch=newton

.. |slack badge| image:: https://f5-openstack-slack.herokuapp.com/badge.svg
    :target: https://f5-openstack-slack.herokuapp.com/
    :alt: Slack

.. |coveralls badge| image:: https://coveralls.io/repos/github/F5Networks/f5-openstack-agent/badge.svg?branch=newton
    :target: https://coveralls.io/github/F5Networks/f5-openstack-agent?branch=newton
    :alt: Coveralls
