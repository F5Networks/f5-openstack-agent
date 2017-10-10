F5 Agent for OpenStack Neutron
==============================

.. sidebar:: **OpenStack version:**

   |openstack|

|Build Status|

.. raw:: html

    <script async defer src="https://f5-openstack-slack.herokuapp.com/slackin.js"></script>


.. toctree::
   :hidden:
   :caption: Contents
   :maxdepth: 1
   :glob:

   config-file
   global-routed-mode
   l2-adjacent-mode
   device-driver-settings
   ha-mode


version |release|
-----------------

|release-notes|

The |agent-long| (``f5-openstack-agent``) is an OpenStack `Neutron plugin agent <https://docs.openstack.org/security-guide/networking/architecture.html>`_.
It works in conjunction with the `F5 Driver for OpenStack LBaaS </products/openstack/lbaasv2-driver/latest/index.html>`_ to manage F5 BIG-IP `Local Traffic Manager <https://f5.com/products/big-ip/local-traffic-manager-ltm>`_ (LTM) services via the OpenStack Neutron API.

.. seealso::

   For more information about how the |agent-short| interacts with the Neutron API and BIG-IP devices, see :ref:`Architecture`.


.. index::
   triple: f5-openstack-agent; downloads; debian
   triple: f5-openstack-agent; downloads; rpm

Downloads
---------

|deb-download| |rpm-download|


Guides
------

See the `F5 Integration for OpenStack`_ user documentation.

.. index::
   single: f5-openstack-agent; install

.. _agent-installation:

.. _Install the F5 Agent:

Installation
------------

Follow the instructions for your distribution to install the |agent-long| on your Neutron controller.

.. tip::

   You can use the `f5-openstack-ansible`_ project to deploy the |agent-short|, |driver-long|, and all project dependencies.
   See `Deploy OpenStack Agent and Driver with Ansible`_ for more information.

.. index::
   triple: f5-openstack-agent; install; debian

Debian
``````

#. Download |agent| and its dependencies (``f5-icontrol-rest-python`` and ``f5-common-python``).
#. Install all three (3) packages.

   .. parsed-literal::

      curl -L -O |f5_agent_deb_url|
      curl -L -O |f5_sdk_deb_url|
      curl -L -O |f5_icontrol_deb_url|
      dpkg –i |f5_icontrol_deb_package|
      dpkg –i |f5_sdk_deb_package|
      dpkg –i |f5_agent_deb_package|

.. index::
   triple: f5-openstack-agent; install; pip

Pip
```

Install the |agent| release package from GitHub.

.. parsed-literal::

   pip install |f5_agent_pip_url|


.. tip::

   Use ``@<branch-name>`` to install from HEAD on a specific branch.

   For example:

   .. parsed-literal::

      pip install |f5_agent_pip_url_branch|


.. index::
   triple: f5-openstack-agent; install; rpm


RPM
```

#. Download |agent| and its dependencies (``f5-icontrol-rest-python`` and ``f5-common-python``).
#. Install all three (3) packages.

   .. parsed-literal::

      curl -L -O |f5_sdk_rpm_url|
      curl -L -O |f5_icontrol_rpm_url|
      curl -L -O |f5_agent_rpm_url|
      rpm -ivh |f5_icontrol_rpm_package| |f5_sdk_rpm_package| |f5_agent_rpm_package|

Next Steps
``````````

- `Install the F5 LBaaSv2 Driver`_.
- :ref:`Configure the F5 Agent <configure-the-f5-openstack-agent>`.

.. index::
   single: f5-openstack-agent; architecture

.. _architecture:

Architecture
------------

The |driver-long| assigns LBaaS tasks from the Neutron RPC Messaging queue to the |agent-long|.
The |agent-short| translates the Neutron LBaaS API calls to iControl REST API calls and `configures the requested objects`_ on the BIG-IP device(s) identified in the :ref:`F5 Agent Configuration File <agent-config-file>`.

When the |agent-short| and |driver-short| run on your OpenStack Neutron Controller, you can use the standard ``neutron lbaas`` commands to manage BIG-IP LTM objects. [#neutroncli]_
The table below shows the corresponding iControl endpoint and BIG-IP object for each :code:`neutron lbaas-* create` command.

.. table:: OpenStack Neutron to F5 iControl REST/BIG-IP command mapping

   ========================================== ============================================================================================ ==================================
   Command                                    URI                                                                                          Configurations Applied
   ========================================== ============================================================================================ ==================================
   :code:`neutron lbaas-loadbalancer-create`  ``https://<icontrol_endpoint>:443/mgmt/tm/sys/folder/~Project_<os_tenant_id>``               Creates new BIG-IP partition;
                                                                                                                                           name uses the OpenStack uuid and
                                                                                                                                           tenant ID
   ------------------------------------------ -------------------------------------------------------------------------------------------- ----------------------------------
   :code:`neutron lbaas-listener-create`      ``https://<icontrol_endpoint>:443/mgmt/tm/ltm/virtual/``                                     Creates new BIG-IP virtual server
                                                                                                                                           in the tenant's partition
   ------------------------------------------ -------------------------------------------------------------------------------------------- ----------------------------------
   :code:`neutron lbaas-pool-create`          ``https://<icontrol_endpoint>:443/mgmt/tm/ltm/pool/``                                        Creates new pool on the virtual
                                                                                                                                           server
   ------------------------------------------ -------------------------------------------------------------------------------------------- ----------------------------------
   :code:`neutron lbaas-member-create`        ``https://<icontrol_endpoint>:443/mgmt/tm/ltm/pool/~Project_<os_tenant_id>~pool1/members/``  Creates new pool member on the
                                                                                                                                           virtual server
   ------------------------------------------ -------------------------------------------------------------------------------------------- ----------------------------------
   :code:`neutron lbaas-healthmonitor-create` ``https://<icontrol_endpoint>:443/mgmt/tm/ltm/monitor/http/``                                Creates new health monitor for the
                                                                                                                                           pool
   ========================================== ============================================================================================ ==================================

.. index::
   single: f5-openstack-agent; supported features

.. _agent-supported-features:

Modes of Operation
------------------

.. seealso::

   See `F5 Agent modes`_ for detailed information regarding each of the Agent's modes of operation and example use cases.

* :ref:`Run the F5 Agent in global routed mode <global-routed-setup>`
* :ref:`Run the F5 Agent in L2-adjacent mode <l2-adjacent-setup>`


.. index::
   single: f5-openstack-agent; configure

.. _configure-the-f5-openstack-agent:

Configure the F5 Agent
----------------------

.. seealso::

   View the :ref:`F5 Agent Configuration parameters <agent-config-parameters>` for detailed explanations of the available options.
   The settings you apply in the configuration file should reflect your existing network architecture and BIG-IP system configurations.

#. Use your text editor of choice to edit the :ref:`F5 Agent Configuration File` as appropriate for your environment.

   .. code-block:: console

      vim /etc/neutron/services/f5/f5-openstack-agent.ini

.. _topic-start-the-agent:

#. Start the |agent-short|.

   .. include:: /_static/reuse/start-the-agent.rst

.. index::
   single: f5-openstack-agent; configuration file examples

.. _agent-config-examples:
.. _agent-config-file-example:

Configuration File Examples
---------------------------

The example configuration files provided here can help guide you in setting up the |agent-short|.

.. rubric:: Global routed mode

* :download:`Download global routed mode example </_static/config_examples/f5-openstack-agent.grm.ini>`

.. rubric:: L2-adjacent mode

* :download:`GRE example </_static/config_examples/f5-openstack-agent.gre.ini>`
* :download:`VLAN example </_static/config_examples/f5-openstack-agent.vlan.ini>`
* :download:`VXLAN example </_static/config_examples/f5-openstack-agent.vxlan.ini>`

.. index::
   single: f5-openstack-agent; unsupported features

.. _f5-agent-unsupported-features:

Unsupported Features
--------------------

The items shown in the table below are not supported in the current release.

.. table:: Unsupported Features in |release|

   =======================================   ==================================
   Feature                                   Project
   =======================================   ==================================
   `Distributed Virtual Router`_ (DVR)       Neutron
   ---------------------------------------   ----------------------------------
   `Role Based Access Control`_ (RBAC)       Neutron
   ---------------------------------------   ----------------------------------
   Agent High Availability (HA) [#agent]_    F5 OpenStack
   =======================================   ==================================

.. index::
   single: f5-openstack-agent; upgrade

.. _agent-upgrade:

Upgrade
-------

Before you can upgrade to/install a different version of |agent|, you need to **uninstall your current version**.
Perform the steps below on every server running |agent-short|.

.. danger::

   If you use ``pip install --upgrade`` to upgrade the F5 LBaaSv2 agent, packages that other OpenStack components use might be negatively impacted.
   F5 does not recommend using ``pip install --upgrade`` to upgrade the |agent| package.

#. Copy the |agent-short| configuration file to a different directory (for example, :file:`~/f5-upgrade-temp`).

   .. warning::

      Your configuration file (:file:`/etc/neutron/services/f5/f5-openstack-agent.ini` gets overwritten when you install a new package.
      If you don't save a copy elsewhere, you will lose your config settings.

   .. code-block:: bash

      $ cp /etc/neutron/services/f5/f5-openstack-agent.ini ~/f5-upgrade-temp

#. Move or rename the |agent-short| log file.

   Your new |agent-short| will not start if it finds an existing |agent| .log file.
   You can either move the log file to a new location, or rename it.

   .. code-block:: bash

      $ mv /var/log/neutron/f5-openstack-agent.log ~/f5-upgrade-temp

#. Stop and remove the current version of the |agent-short|.

   .. code-block:: bash
      :caption: Debian/Ubuntu

      $ sudo service f5-oslbaasv2-agent stop
      $ pip uninstall f5-openstack-agent

   .. code-block:: bash
      :caption: Red Hat/CentOS

      $ sudo systemctl stop f5-openstack-agent
      $ sudo systemctl disable f5-openstack-agent
      $ sudo pip uninstall f5-openstack-agent

#. Follow the :ref:`installation <agent-installation>` instructions to install a different version of the |agent-short|.

#. Copy your configuration file back into :file:`/etc/neutron/services/f5`.

   .. tip::

      It's good practice to compare your saved copy of the configuration file with the new one created during installation.
      Verify that the only differences between the two are those required for your deployment.
      If new options appear in the config file, see :ref:`supported features <agent-supported-features>` and :ref:`configuration parameters <agent-config-parameters>` for explanations and config instructions.

   .. code-block:: bash

      $ cp ~/f5-upgrade-temp/f5-openstack-agent.ini /etc/neutron/services/f5/f5-openstack-agent.ini


.. rubric:: Footnotes
.. [#neutroncli] See the `Neutron LBaaS documentation <https://docs.openstack.org/mitaka/networking-guide/config-lbaas.html>`_
.. [#agent] Similar to BIG-IP :term:`high availability`, but applies to the |agent-short| processes.

.. |Build Status| image:: https://travis-ci.org/F5Networks/f5-openstack-agent.svg?branch=liberty
   :target: https://travis-ci.org/F5Networks/f5-openstack-agent
   :alt: Travis-CI Build Status
.. _OpenStack provider network: https://docs.openstack.org/newton/networking-guide/intro-os-networking.html#provider-networks
.. _Address Resolution Protocol: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/11.html
.. _Neutron Modular Layer 2: https://wiki.openstack.org/wiki/Neutron/ML2
.. _BIG-IP route domains: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/8.html
.. _BIG-IP SNAT pools: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/7.html
.. _OpenStack Barbican: https://wiki.openstack.org/wiki/Barbican
.. _OpenStack Keystone: https://wiki.openstack.org/wiki/Keystone
.. _Binds VLANs to BIG-IP interfaces: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/4.html
.. _automap SNAT: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/7.html
.. _configures the requested objects: /cloud/openstack/latest/lbaas/bigip-command-mapping.html
.. _Distributed Virtual Router: https://specs.openstack.org/openstack/neutron-specs/specs/juno/neutron-ovs-dvr.html
.. _Role Based Access Control: http://specs.openstack.org/openstack/neutron-specs/specs/liberty/rbac-networks.html
.. _f5-openstack-ansible: https://github.com/f5devcentral/f5-openstack-ansible
.. _Deploy OpenStack Agent and Driver with Ansible: https://github.com/f5devcentral/f5-openstack-ansible/blob/master/playbooks/AGENT_DRIVER_DEPLOY.rst
