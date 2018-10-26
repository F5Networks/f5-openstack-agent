.. _agent-config-file:
.. _F5 Agent Configuration File:

F5 Agent Configuration File
===========================

The :ref:`F5 Agent Configuration File <agent-config-file-example>` -- :file:`/etc/neutron/services/f5/f5-openstack-agent.ini` -- tells the |agent-long| about the network architecture and how/where the BIG-IP device(s) fit in.

The configuration parameters tell the agent:

a) where to find your BIG-IP device(s), and
b) how the BIG-IP system is already set up.

The latter impacts how the |agent-short| configures BIG-IP objects in response to Neutron API calls.

.. important::

   Use the appropriate |agent-short| configuration parameters for your network architecture and existing BIG-IP configurations.

The |agent-short| has two (2) modes of operation: :ref:`Global routed mode <global-routed-setup>`, :ref:`L2-adjacent mode <l2-adjacent-setup>`.
The mode you should use depends on how your BIG-IP device(s) connects to the network.

* Global routed mode -- use if the BIG-IP device(s) connects directly to the `OpenStack provider network`_.
* L2-adjacent mode -- use if your BIG-IP device(s) or Virtual Edition (VE) instance(s) connects to the provider network via VLANs and/or VXLAN/GRE tunnels.

.. seealso:: 

   Unsure which mode to use? See `F5 Agent modes`_ for more information.

.. _agent-config-parameters:

F5 Agent configuration parameters
---------------------------------
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
                                                            plugin;
                                                            used to identify F5 agent
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

                                                                                                FALSE: BIG-IP devices use VLANs, VXLAN
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
f5_common_networks              boolean                     Controls where the agent creates    TRUE: the agent creates all network objects TRUE
                                                            network objects                     in the :code:`/Common` partition on the
                                                                                                BIG-IP system.
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
f5_bigip_lbaas_device_driver    string                      The iControl device driver          **DO NOT CHANGE THIS SETTING.**
------------------------------- --------------------------- ----------------------------------- ------------------------------------------- ---------------------
icontrol_hostname               string                      The IP address, or DNS-resolvable   single item or comma-separated list         N/A
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

   The settings in this section only apply if you are use `OpenStack Barbican`_ for authentication. If you aren't using Barbican, leave this section commented out.

=============================== =========================== =================================== =========================================== =====================
Parameter	                    Type	                     Description	                        Allowed Values                              Recommended Value
=============================== =========================== =================================== =========================================== =====================
cert_manager                    string                      the F5 agent's BarbicanCertManager  ``f5_openstack_agent.lbaasv2.drivers.bigip. None / leave empty
                                                                                                barbican_cert.BarbicanCertManager``

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

.. _OpenStack provider network: https://docs.openstack.org/newton/networking-guide/intro-os-networking.html#provider-networks
.. _Address Resolution Protocol: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/11.html
.. _Neutron Modular Layer 2: https://wiki.openstack.org/wiki/Neutron/ML2
.. _BIG-IP route domains: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/8.html
.. _BIG-IP SNAT pools: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/7.html
.. _OpenStack Barbican: https://wiki.openstack.org/wiki/Barbican
.. _OpenStack Keystone: https://wiki.openstack.org/wiki/Keystone
.. _Binds VLANs to BIG-IP interfaces: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/4.html
.. _automap SNAT: https://support.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/tmos-routing-administration-13-0-0/7.html
