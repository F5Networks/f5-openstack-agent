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

Installation
------------

Follow the instructions for your distribution below to install the |agent-long| on your Neutron controller.

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

- `Install the F5 driver for OpenStack LBaaSv2 </products/cloud/f5-openstack-lbaasv2-driver/latest/index.html#installation>`_.
- :ref:`Configure the F5 Agent for OpenStack Neutron <configure-the-f5-openstack-agent>`.

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

* :ref:`Global Routed Mode <global-routed-mode>`
* :ref:`L2/L3-Adjacent Mode <l2-adjacent-mode>`


.. index::
   single: f5-openstack-agent; configure

.. _configure-the-f5-openstack-agent:

Configure the |agent-long|
--------------------------

#. Use your text editor of choice to edit the :ref:`F5 Agent Configuration File` as appropriate for your environment.

   .. code-block:: console

      vim /etc/neutron/services/f5/f5-openstack-agent.ini

.. _topic-start-the-agent:

#. Start the |agent-short|.

   Once you have configured the |agent-short|, you can use the appropriate command(s) for your OS to start or stop the agent service.

   .. rubric:: CentOS
   .. code-block:: console

      systemctl enable f5-openstack-agent
      systemctl start f5-openstack-agent
      systemctl stop f5-openstack-agent.service

   .. rubric:: Ubuntu
   .. code-block:: console

      service f5-oslbaasv2-agent start
      service f5-oslbaasv2-agent stop


.. _agent-config-file:
.. _F5 Agent Configuration File:

F5 Agent Configuration File
---------------------------

The :ref:`F5 Agent Configuration File <agent-config-file-example>` (:file:`/etc/neutron/services/f5/f5-openstack-agent.ini`) tells the |agent-long| about the network architecture and how/where the BIG-IP device(s) fit in.
The configuration parameters tell the agent:

a) where to find the BIG-IP device(s) you expect it to manage, and
b) what settings are already applied on the BIG-IP device(s).

The latter impacts how the |agent-short| configures BIG-IP objects in response to Neutron API calls.

.. important::

   Use the appropriate |agent-long| configuration parameters for your network architecture and existing BIG-IP configurations.

The |agent-long| has two (2) modes of operation: :ref:`Global routed mode <global-routed-mode>` and :ref:`L2/L3-adjacent mode <l2-adjacent-mode>`.
The mode you should use depends on where your BIG-IP device(s) reside in the network architecture.

* Global routed mode -- use with BIG-IP hardware devices that connect directly to the `OpenStack provider network`_.
* L2/L3-adjacent mode -- if your BIG-IP devices or Virtual Edition (VE) instances connect to the provider network via VLANs and/or VXLAN/GRE tunnels.


.. _agent-config-parameters:

Each section below corresponds to a section of the :ref:`F5 Agent Configuration File`.

.. index::
   single: f5-openstack-agent; default settings

.. _default-settings:

DEFAULT SETTINGS
````````````````

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
debug                           boolean                     Sets the log level to DEBUG.        True, False                                 True
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
periodic_interval               integer                     Sets the number of seconds between  Any number of seconds, expressed as an      Default=10
                                                            the agent's attempts to sync its    integer
                                                            state with Neutron
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
service_resync_interval         integer                     Sets the frequency at which the     Any number of seconds, expressed as an      Default=500
                                                            agent discards its service cache    integer
                                                            and syncs with the Neutron LBaaS
                                                            service.
=============================== =========================== =================================== =========================================== =====================

.. index::
   single: f5-openstack-agent; environment settings

.. _environment-settings:

ENVIRONMENT SETTINGS
````````````````````

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
environment_prefix              string                      Sets the default prefix applied     Any string beginning with an alpha          Default=Project
                                                            to all BIG-IP LTM objects           character.
                                                            in the tenant partition.
=============================== =========================== =================================== =========================================== =====================


.. index::
   single: f5-openstack-agent; static agent configuration settings

.. _static-agent-data-settings:

STATIC AGENT CONFIGURATION SETTINGS
```````````````````````````````````

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
static_agent_configuration_data key-value pair              Defines static agent identification single key-value pair --OR--                N/A
                                                            data sent to the Neutron LBaaS      comma-separated list of key-value pairs
                                                            plugin; used to identify agent
                                                            for custom pool-to-agent
                                                            scheduling.
=============================== =========================== =================================== =========================================== =====================

.. index::
   single: f5-openstack-agent; device settings

.. _device-settings:

DEVICE SETTINGS
```````````````

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
f5_ha_type                      string                      Defines the BIG-IP device high      - standalone: single BIG-IP device          Default=standalone
                                                            availability (HA) mode.             - pair: active/standby pair (2 BIG-IP
                                                                                                  devices)
                                                                                                - scalen: active/active device cluster
                                                                                                  (3 or more BIG-IP devices)
=============================== =========================== =================================== =========================================== =====================

.. index::
   single: f5-openstack-agent; L2 segmentation mode settings

.. _l2-segmentation-settings:

L2 SEGMENTATION MODE SETTINGS
`````````````````````````````

==================================== ====================== =================================== =========================================== =====================
Parameter	                         Type	                  Description	                        Allowed Values                              Recommended Value
==================================== ====================== =================================== =========================================== =====================
f5_external_physical_mappings        string                 `Binds VLANs to BIG-IP interfaces`_ string in the format                        Default=
                                                            ; tells the agent about the         "physical_network:interface_name:tagged"    default:1.1:True
                                                            interface's VLAN tagging
                                                            settings                            The agent will use the "default" mapping
                                                                                                if you don't define mappings for
                                                                                                specific VLANs.

                                                                                                Example:
                                                                                                "ext_net:1.1:True" -- maps the external
                                                                                                physical network named "ext_net" to
                                                                                                BIG-IP interface 1.1; tells the agent
                                                                                                that 1.1 is a tagged interface.

                                                                                                Tagged interfaces accept traffic from
                                                                                                multiple VLANs. Untagged interfaces accept
                                                                                                traffic from a single VLAN.
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
vlan_binding_driver                  string                 Software hook allowing              The vlan_binding_driver allows you to bind  N/A
                                                            VLAN-interface-port mapping         and prune VLAN ids to specific ports.

                                                                                                A vlan_binding_driver class must:

                                                                                                - reference a subclass of
                                                                                                  :py:class:`VLANBindingBase`
                                                                                                - contain methods that bind and prune
                                                                                                  VLAN tags to specific ports
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
interface_port_static_mappings       JSON dictionary        Enabled by vlan_binding_driver;     JSON dictionaries mapping BIG-IP devices    N/A
                                                            maps BIG-IP devices and interfaces  and interfaces to ports.
                                                            to specific ports
                                                                                                Follows the format
                                                                                                "{"device_name":{"interface_id":"port_id"}"
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_vtep_folder                       string                 The BIG-IP partition containing     N/A                                         /Common
                                                            the desired `VTEP`_ .
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_vtep_selfip_name                  string                 The name of the BIG-IP self IP to   N/A                                         vtep
                                                            use as the VTEP.
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
advertised_tunnel_types              string                 The type of tunnel to use.          vxlan, gre                                  vxlan

                                                            The agent advertises its ability
                                                            to terminate this tunnel type
                                                            via the oslo ``tunnel_sync``
                                                            message queues. The agent
                                                            registers BIG-IP devices as tunnel
                                                            peers based on this setting.

                                                            This setting must be the same on
                                                            all OpenStack nodes (controller,
                                                            compute, and network).
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_populate_static_arp               boolean                Controls BIG-IP                     TRUE: the agent adds static entries         TRUE
                                                            `Address Resolution Protocol`_      for the IP and MAC addresses in the
                                                            (ARP) settings.                     Neutron LBaaS service definition to the
                                                                                                BIG-IP system ARP cache.

                                                                                                FALSE: the agent discovers BIG-IP pool
                                                                                                members via flooding.
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
l2_population                        boolean                Sets agent registration policy      TRUE: the agent registers for ml2           TRUE
                                                            for `Neutron Modular Layer 2`_      population messages; these allow the agent
                                                            (ml2) messages                      to update the VTEP forwarding table when
                                                                                                pool members migrate from one compute
                                                                                                node to another.

                                                                                                FALSE: the agent does not receive ml2
                                                                                                population messages and does not update
                                                                                                VTEP table entries for migrated pool
                                                                                                members.
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_network_segment_physical_network  string                 The network segment the agent       String; must be the name of the network     N/A
                                                            should watch.                       segment you want the agent to watch for
                                                                                                dynamically-created VLANs.

                                                                                                Used in conjunction with software-defined
                                                                                                networking (SDN).

                                                                                                Comment out this setting if
                                                                                                you are not using hierarchical port
                                                                                                binding. [#hpb]_
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_network_segment_polling_interval  integer                The frequency at which the agent    integer; in seconds                         10
                                                            should poll for disconnected LBaaS
                                                            listeners. [#hpb]_                  Comment out this setting if
                                                                                                you are not using hierarchical port
                                                                                                binding.
------------------------------------ ---------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_pending_services_timeout          integer                Maximum amount of time before       integer; in seconds                         60
                                                            creation of a pending service
                                                            errors out. [#hpb]_                 Comment out this setting if
                                                                                                you are not using hierarchical port
                                                                                                binding.
==================================== ====================== =================================== =========================================== =====================

.. rubric:: Footnotes
.. [#hpb] See `Hierarchical Port Binding`_.

.. index::
   single: f5-openstack-agent; L3 segmentation mode settings

.. _l3-segmentation-settings:

L3 SEGMENTATION MODE SETTINGS
`````````````````````````````

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
f5_global_routed_mode           boolean                     Defines how the BIG-IP devices      TRUE: BIG-IP device(s) connect directly to  FALSE
                                                            connect to the network              the `OpenStack provider network`_.
                                                                                                (**L2 routing only**)

                                                                                                FALSE: BIG-IP devices use VXLAN
                                                                                                or GRE tunnels to bridge physical/
                                                                                                virtualized network segments.
                                                                                                (**L2 & L3 routing**; "L2-adjacent mode")
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
use_namespaces                  boolean                     Tells the agent if you're using     TRUE: you're using BIG-IP route domains     TRUE
                                                            `BIG-IP route domains`_             to segment tenant network traffic.
                                                                                                                                            Forced to FALSE if
                                                                                                FALSE: you're not using route domains;      f5_global_routed_mode
                                                                                                tenant networks cannot use overlapping      = TRUE
                                                                                                subnets.
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
max_namespaces_per_tenant       integer                     Sets the maximum number of          Any integer, with the caveat that using     1
                                                            namespaces/route tables the agent   more than 1 namespace per tenant is NOT
                                                            can allocate per tenant             a recommended practice.
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_route_domain_strictness      boolean                     Controls the agent's access to      TRUE: the agent can only access BIG-IP      FALSE
                                                            BIG-IP global routing table         tenant route domains; it cannot consult the
                                                            (route domain ``0``)                global routing table. VIPs and members
                                                                                                can only communicate if they are in the
                                                                                                same tenant.

                                                            Requires                            FALSE: the agent can look for a destination
                                                            ``use_namespaces=TRUE``             route in the global routing table if it
                                                                                                can't find a match in the tenant route
                                                                                                domains. VIPs and members can communicate
                                                                                                across tenants.

                                                                                                Set to FALSE to ensure the agent has access
                                                                                                to external routes on the
                                                                                                `OpenStack provider network`_.
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_snat_mode                    boolean                     Tells the agent if it should        TRUE: the agent manages a SNAT pool for the TRUE
                                                            allocate `BIG-IP SNAT pools`_       tenant.
                                                            for tenants                                                                     Forced to TRUE if
                                                                                                When set to TRUE, incoming proxy traffic    f5_global_routed_mode
                                                                                                uses IP addresses from the SNAT pool.       = TRUE

                                                                                                Set to TRUE when:

                                                                                                - you want to ensure that server responses
                                                                                                  always return through the BIG-IP system
                                                                                                - you want to hide the source addresses of
                                                                                                  server-initiated requests from external
                                                                                                  devices.

                                                                                                FALSE: the agent doesn't allocate a SNAT
                                                                                                pool for the tenant; source IP addresses
                                                                                                for outgoing traffic are not masked;
                                                                                                incoming traffic follows the destination
                                                                                                server's default route.

                                                                                                When set to FALSE, the BIG-IP device sets
                                                                                                up a floating IP as the subnet's default
                                                                                                gateway address and creates a wildcard IP-
                                                                                                forwarding virtual server on the
                                                                                                member's network. Neutron floating IPs will
                                                                                                not work if the BIG-IP device isn't used
                                                                                                as the Neutron Router.
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_snat_addresses_per_subnet    integer                     Defines how many IP addresses       Any integer.                                0
                                                            to allocate in a SNAT pool
                                                                                                Set to ``0`` to use `automap SNAT`_ (the
                                                                                                BIG-IP device automatically creates a SNAT
                                                                                                pool for you).
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
f5_common_external_networks     boolean                     Controls the agent's access to      TRUE: the agent adds all provider           TRUE
                                                            external (infrastructure-based)     networks with ``route:external`` set
                                                            routes                              to ``true`` to the BIG-IP global route
                                                                                                domain (``0``).

                                                                                                Set to TRUE if you want the agent to
                                                                                                route traffic to IP addresses associated
                                                                                                with an external route
                                                                                                (for example, an infrastructure router).

                                                                                                FALSE: the agent cannot route traffic to
                                                                                                provider networks with ``route:external``
                                                                                                set to ``true``.
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
common_networks                 key-value pair              Tells the agent about shared        single key-value pair --OR--                N/A
                                                            networks already configured on      comma-separated list of key-value pairs
                                                            the BIG-IP device
                                                                                                Follows the format
                                                                                                "neutron_network_uuid:BIG-IP_network_name"
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
l3_binding_driver               string                      Software hook allowing              Allows you to bind L3 addresses to specific f5_openstack_agent.
                                                            L3_address-port binding             ports.                                      lbaasv2.drivers.bigip.
                                                                                                                                            l3_binding.
                                                                                                                                            AllowedAddressPairs
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
l3_binding_static_mappings      JSON dictionary             Using the l3_binding_driver,        JSON-encoded dictionary; follows the format N/A
                                                            maps Neutron subnet ids to L2
                                                            ports and devices                   'subnet_id':[('port_id','BIG-IP_device')
=============================== =========================== =================================== =========================================== =====================

.. index::
   single: f5-openstack-agent; device driver/iControl driver settings

.. _driver-settings:

DEVICE DRIVER/iCONTROL DRIVER SETTINGS
``````````````````````````````````````

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
f5_bigip_lbaas_device_driver    string                      The iControl device driver          DO NOT CHANGE THIS SETTING FROM THE DEFAULT
                                                                                                VALUE.
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
icontrol_hostname               string                      The IP address, or DNS-resolvable   single or comma-separated list              N/A
                                                            hostname, of your BIG-IP device(s)
                                                            and/or vCMP guest(s)
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
icontrol_vcmp_hostname          string                      The IP address of your vCMP host    single IP address                           N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
icontrol_username               string                      The username of an account on the   The username of an account with             N/A
                                                            BIG-IP device                       permission to create partitions and
                                                                                                create/manage Local Traffic and Network
                                                                                                objects
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
icontrol_password               string                      Password for the BIG-IP user        See BIG-IP password requirements.           N/A
                                                            account
=============================== =========================== =================================== =========================================== =====================

.. index::
   single: f5-openstack-agent; certificate manager settings

.. _cert-manager-settings:

CERTIFICATE MANAGER SETTINGS
````````````````````````````

.. important::

   The settings in this section only apply if you are using the `OpenStack Barbican`_ service. If you aren't using Barbican, leave this section commented out.

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                    Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
cert_manager                    string                      the agent BarbicanCertManager       f5_openstack_agent.lbaasv2.drivers.bigip.   Default=None
                                                            driver                              barbican_cert.BarbicanCertManager
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
auth_version                    string                      `OpenStack Keystone`_ auth version  v2, v3                                      N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
os_auth_url                     string                      Keystone auth URL                                                               N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
os_username                     string                      OpenStack username                                                              N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
os_password                     string                      OpenStack password                                                              N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
os_user_domain_name             string                      OpenStack user account domain                                                   N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
os_project_name                 string                      OpenStack project (tenant) name                                                 N/A
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
os_project_domain_name          string                      OpenStack project domain                                                        N/A
=============================== =========================== =================================== =========================================== =====================

.. index::
   single: f5-openstack-agent; configuration file examples

.. _agent-config-examples:
.. _agent-config-file-example:

Configuration File Examples
---------------------------

The example configuration files provided here can help guide you in setting up the |agent-long| to work with your specific environment.

.. rubric:: Global routed mode

* :download:`Download global routed mode example </_static/config_examples/f5-openstack-agent.grm.ini>`

.. rubric:: L2-adjacent mode

* :download:`Download GRE example </_static/config_examples/f5-openstack-agent.gre.ini>`
* :download:`Download VLAN example </_static/config_examples/f5-openstack-agent.vlan.ini>`
* :download:`Download VXLAN example </_static/config_examples/f5-openstack-agent.vxlan.ini>`


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

To upgrade to/install a different version of |agent|, you'll need to uninstall your current version first.
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
