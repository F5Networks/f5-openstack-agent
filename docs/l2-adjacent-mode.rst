.. _l2-adjacent-setup:

.. index::
   single: f5-openstack-agent; L2-adjacent mode

L2-adjacent mode
================

L2-adjacent mode (:code:`f5_global_routed_mode = False`) is the default mode of operation for the |agent-long| (F5 agent).
The |agent-short| **does not automatically detect any network or BIG-IP configurations**.
You must provide the appropriate L2/L3 network settings for your BIG-IP device(s) in the :ref:`L2 segmentation mode <l2-segmentation-settings>` and :ref:`L3 segmentation mode <l3-segmentation-settings>` sections of the |agent-short| :ref:`configuration file <agent-config-file>`.

:fonticon:`fa fa-chevron-right` :ref:`Learn more <learn-lam>`

Prerequisites
-------------

You should have VLANs and VxLAN or GRE tunnels configured as appropriate for your environment.
If you're using GRE or VxLAN tunnels, you must have a BIG-IP `Better or Best license`_ that supports SDN.

.. warning::

   Many L3 segmentation mode parameters depend on other configuration parameters.
   Read the text in the :ref:`F5 agent configuration file` carefully before changing these settings to ensure they don't conflict.

Configuration
-------------

.. include:: /_static/reuse/edit-agent-config-file.rst

.. seealso::

   * :fonticon:`fa fa-download` :download:`Sample Configuration file for GRE </_static/config_examples/f5-openstack-agent.gre.ini>`
   * :fonticon:`fa fa-download` :download:`Sample Configuration file for VXLAN </_static/config_examples/f5-openstack-agent.vxlan.ini>`

#. Set up the :ref:`Device driver settings <device-driver-settings>` and :ref:`HA mode <ha-mode>`.

#. Set up the appropriate L2- and L3-segmentation settings for your deployment.

.. _l2-segmentation-mode:

Interface and port mapping
``````````````````````````

:code:`f5_external_physical_mappings`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Maps Neutron networks with type :code:`VLAN` to a specific BIG-IP interface.
It follows the format :code:`physical_network:interface_name:tagged`, where:

* :code:`physical_network` is the `external provider network`_ (Neutron's :code:`provider:physical_network`).
* :code:`interface_name` is the name of a BIG-IP interface or LAG trunk.
* :code:`tagged` is a boolean indicating whether or not the BIG-IP should enforce VLAN tagging.

.. code-block:: text

  # standalone example:
  f5_external_physical_mappings = default:1.1:True
  #
  # pair or scalen example:
  f5_external_physical_mappings = default:1.3:True

.. note::

   If using pair or scalen on a 3-NIC device, use interface 1.3.
   Interface 1.1 usually maps to an external VLAN and 1.2 to internal VLANs.

:code:`vlan_binding_driver`
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Binds tagged VLANs to specific BIG-IP ports.
For example, if an LBaaS iControl endpoint uses tagged VLANs, and you add a VLAN tagged network to a specific BIG-IP device, the facing switch port needs to allow traffic for that VLAN tag through to the correct BIG-IP port.

.. caution::

   This setting requires a custom software hook.
   If you choose to write one, keep the following in mind:

   - A :class:`vlan_binding_driver` class must reference an iControl :class:`VLANBindingBase` subclass.
   - You must provide the methods to bind VLAN tags to ports and prune unused VLAN tags.

.. code-block:: text

   # the path to your custom software hook
   vlan_binding_driver = f5-openstack-agent.drivers.bigip.vlan_binding.MyBindingDriver

.. _device-tunneling-vtep:

Tunneling
`````````

:code:`f5_vtep_`
~~~~~~~~~~~~~~~~

:code:`f5_vtep_folder`: The name of the BIG-IP :term:`partition` in which the `VTEP`_ (VxLAN tunnel endpoint) resides; the default partition is ``/Common``.
:code:`f5_vtep_selfip_name`: The name of the VTEP self IP.

Can be a single entry or a comma-separated list (one per BIG-IP device); must be in cidr (h/m) format.
The VTEP self IPs must already exist on the BIG-IP device(s).

.. code-block:: text

   # Device Tunneling (VTEP) selfips
   #
   f5_vtep_folder = Common
   f5_vtep_selfip_name = my_vtep
   #

.. hint::

   If you're not using GRE or VxLAN tunneling, you can comment these settings out or set both to ``None``.

:code:`advertised_tunnel_types`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tells the |agent-short| what type of tunnel(s) connect the BIG-IP device(s) to controller/compute node(s) in OpenStack (GRE or VxLAN).
This can be a single entry or comma-separated values.
If you are not using tunnels, leave this setting blank.

.. note::

   The |agent-long| creates profiles for all available tunnel types on the BIG-IP device(s) when you start it for the first time.
   See `Neutron to BIG-IP command mapping </cloud/openstack/latest/lbaas/bigip-command-mapping.html>`_ for more information.


.. code-block:: text

   # Tunnel types
   #
   # If you are using only gre tunnels:
   #
   advertised_tunnel_types = gre
   #
   # If you are using only vxlan tunnels:
   #
   advertised_tunnel_types = vxlan
   #
   # If you are using both gre and vxlan tunnel networks:
   #
   advertised_tunnel_types = gre,vxlan
   #
   # If you are NOT using tunnel networks (vlans only):
   #
   advertised_tunnel_types =
   #

Routing
```````

.. _static-arp:

:code:`f5_populate_static_arp`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A boolean indicating whether or not you want to create static arp entries for pool member IP addresses on VxLAN or GRE tunnel networks.

The static ARP entry is in addition to the tunnel forwarding database (FDB) entry for the pool member.
It helps avoid the need to learn the member's MAC address via flooding.

.. code-block:: text

   # Static ARP population for members on tunnel networks
   #
   f5_populate_static_arp = True
   #

:code:`l2_population`
~~~~~~~~~~~~~~~~~~~~~

A boolean indicating whether or not the BIG-IP device should use the L2 population service to update FBD tunnel entries.

.. important::

   If you're running any other OpenStack tunnel agents, be sure to set all of them up the same way.

.. code-block:: text

   #
   l2_population = True
   #

:code:`use_namespaces`
~~~~~~~~~~~~~~~~~~~~~~

A boolean indicating whether or not the BIG-IP should use tenant routing tables to route traffic.
Set this value to True to allow overlapping subnet IP addresses.

.. code-block:: text

   #
   use_namespaces = True
   #

:code:`max_namespaces_per_tenant`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An integer indicating the maximum number of route domains allowed per tenant.
This allows a tenant to have overlapping IP subnets.

.. code-block:: text

   #
   max_namespaces_per_tenant = 1
   #

:code:`f5_route_domain_strictness`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A boolean indicating whether VIPS and members in different tenants can communicate with each other.
Set this value to True to force the BIG-IP to prefer tenant routing tables over the global routing table and provide tenant isolation.

.. code-block:: text

   #
   f5_route_domain_strictness = False
   #

:code:`f5_snat_mode`
~~~~~~~~~~~~~~~~~~~~

A boolean indicating whether or not to use `SNATs`_.

:code:`f5_snat_addresses_per_subnet`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An integer indicating the number of `self IP`_ addresses the BIG-IP device should add to a SNAT pool for each subnet.

.. code-block:: text

   #
   f5_snat_mode = True
   #
   f5_snat_addresses_per_subnet = 1
   #

:code:`f5_common_external_networks`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A boolean that controls how the BIG-IP device routes traffic on Neutron networks.
Set this value to True to use the global routing table for traffic on all Neutron networks with the :code:`external` router type.

.. code-block:: text

   #
   f5_common_external_networks = True
   #

.. _common networks:

:code:`common_network_ids`
~~~~~~~~~~~~~~~~~~~~~~~~~~

A 'name-value' pair mapping BIG-IP VLANs to Neutron networks; multiple values can be comma-separated.
The first value is the Neutron network ID; the second is the BIG-IP network name.

For example, if the Internet VLAN on your BIG-IP device, ``/Common/external``, has the Neutron uuid ``71718972-78e2-449e-bb56-ce47cc9d2680``, the entry would look like this:

.. code-block:: text

   # Common Networks
   #
   common_network_ids = 71718972-78e2-449e-bb56-ce47cc9d2680:external
   #

You can separate multiple values with commas, as shown below.

.. code-block:: text

   #
   common_network_ids = 71718972-78e2-449e-bb56-ce47cc9d2680:external,396e06a0-05c7-4a49-8e86-04bb83d14438:vlan1222
   #

.. _l3 binding:

:code:`l3_binding_driver`
~~~~~~~~~~~~~~~~~~~~~~~~~

A software hook that binds L3 addresses to specific ports, allowing communications between Nova guest instances.

.. important::

   If you're managing :term:`overcloud` BIG-IP VE instances, uncomment this line in the F5 Agent Configuration File.

.. code-block:: text

   #
   l3_binding_driver = f5_openstack_agent.lbaasv2.drivers.bigip.l3_binding.AllowedAddressPairs
   #

Software-defined networking
```````````````````````````

:code:`f5_network_segment_physical_network`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The name of the network segment where the BIG-IP device resides.

:code:`f5_network_segment_polling_interval`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The number of seconds to wait between polling Neutron for a :code:`network_id` to :code:`segmentation_id` mapping (default=10).

:code:`f5_pending_services_timeout`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The maximum number of seconds to wait for network discovery before a pending service errors out (default=60).

.. tip::

   These `Hierarchical Port Binding`_ settings allow you to integrate and manage SDN services using F5 LBaaS.
   If you're not using this feature, comment out all three settings, or set them to None, to avoid errors.

.. code-block:: text

   # Hierarchical Port Binding
   #
   f5_network_segment_physical_network = <switch_name>
   #
   # Periodically scan for disconected listeners (a.k.a virtual servers).  The
   # interval is number of seconds between attempts.
   #
   f5_network_segment_polling_interval = 10
   #
   f5_pending_services_timeout = 60
   #

.. _learn-lam:

Learn more
----------

Example Use Case
````````````````

Typically, the |agent-long| manages one (1) or more BIG-IP devices deployed in the services tier of an `external provider network`_.
The BIG-IP devices may have direct lines of communication with nodes in the OpenStack cloud (VXLAN or GRE tunnels) or they may connect to the same VLAN subnet(s) as OpenStack nodes.

.. figure:: /_static/media/f5-lbaas-l2-3-adjacent-mode.png
   :alt: L2-adjacent BIG-IP cluster diagram shows a BIG-IP device cluster as part of an L3-routed network external to the OpenStack cloud. VXLAN or GRE tunnels connect OpenStack nodes directly to the device cluster.
   :width: 60%

   L2-adjacent BIG-IP device cluster

The |agent-short| can also manage BIG-IP Virtual Edition (VE) instances deployed 'over the cloud' (or :term:`overcloud`) using L2-adjacent mode.
These VE instances would connect to individual OpenStack nodes via VLANs, as opposed to VXLAN or GRE tunnels.
This type of deployment is commonly used as part of a software-defined networking (SDN) solution, such as with `Cisco ACI`_.

.. todo:: add Cisco APIC/ACI deployment solution guide and link to it here

.. important::

   The |agent-short| L2/L3 segmentation mode settings must match the configurations of your existing external network and BIG-IP device(s).

Next steps
----------

- If this is your initial launch, :ref:`start the F5 agent <topic-start-the-agent>`.
- If you have updated the configurations for a running |agent-short| , restart the service:

  - CentOS: :command:`systemctl systemctl start f5-openstack-agent`
  - Ubuntu :command:`service f5-oslbaasv2-agent start`

See the `F5 Integration for OpenStack`_ documentation for more information.


