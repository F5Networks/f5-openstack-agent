.. _global-routed-setup:

.. index::
   single: f5-openstack-agent; global routed mode

Global Routed mode
==================

The |agent-long| :ref:`L2 segmentation mode settings <l2-segmentation-settings>` and :ref:`L3 segmentation mode settings <l3-segmentation-settings>` tell the |agent-short| about BIG-IP devices' L2 and L3 network configurations.

:fonticon:`fa fa-chevron-right` :ref:`Learn more <learn-grm>`

Caveats
-------

- In global routed mode, the |agent-long| assumes that all L3 virtual IP addresses are globally routable.
  This means that all virtual IPs listen on all VLANs accessible to the BIG-IP (in other words, there is no VLAN segmentation).
- Global routed mode uses the BIG-IP global route domain (``0``).
  This precludes the use of overlapping subnets/IP addresses amongst tenants.

Configuration
-------------

.. include:: /_static/reuse/edit-agent-config-file.rst

#. Set up the :ref:`Device driver settings <device-driver-settings>` and :ref:`HA mode <ha-mode>`.

#. Define the L2- and L3-segmentation settings for Global Routed Mode.

   .. table:: Global Routed Mode settings

      =================================== =============================================
      Setting                             Description
      =================================== =============================================
      ``global_routed_mode``              Boolean; set to `True` to make all VIPs and
                                          pool members globally routable

      ``use_namespaces``                  Boolean; forced to `False` in global routed
                                          mode.

      ``f5_snat_mode``                    Boolean; forced to `True` in global routed
                                          mode.

                                          Uses automap SNATs to allocate
                                          self IP addresses for LBaaS objects.

      ``f5_snat_addresses_per_subnet``    Integer; forced to ``0`` in global routed
                                          mode; the BIG-IP device's local
                                          self IP is also the SNAT address.

      ``f5_common_external_networks``     Boolean; when `True`, the agent adds all
                                          external Neutron networks to the global
                                          routing table (the BIG-IP `/Common`
                                          :term:`partition`) and route domain ``0``.
      =================================== =============================================

   .. code-block:: text

      ###############################################################################
      #  L3 Segmentation Mode Settings
      ###############################################################################
      #
      # Global Routed Mode - No L2 or L3 Segmentation on BIG-IP
      #
      f5_global_routed_mode = True
      #
      use_namespaces = False
      #
      # SNAT Mode and SNAT Address Counts
      #
      f5_snat_mode = True
      #
      f5_snat_addresses_per_subnet = 0
      #
      f5_common_external_networks = True
      #

   :fonticon:`fa fa-download` :download:`Sample Global Routed Mode configuration file </_static/config_examples/f5-openstack-agent.grm.ini>`

.. _learn-grm:

Learn more
----------

In global routed mode (``f5_global_routed_mode=TRUE``), the |agent-long| assumes the following:

- All LBaaS objects are accessible via global L3 routes.
- All virtual IPs are routable from clients.
- All pool members are routable from BIG-IP devices.

All required L2 and L3 Network objects (including routes) must exist on your BIG-IP devices *before* you deploy the |agent-short| in OpenStack.

.. figure:: /_static/media/f5-lbaas-global-routed-mode.png
   :width: 60%
   :alt: Global routed mode diagram shows a BIG-IP device cluster as part of an L3-routed network external to the OpenStack cloud.

   Global routed mode

Use Case
--------

Global routed mode is generally used for :term:`undercloud` BIG-IP hardware deployments.
The BIG-IP device resides at the services tier in the `external provider network`_.

.. figure:: /_static/media/big-ip_undercloud.png
   :width: 60%
   :alt: Undercloud deployment diagram shows two BIG-IP hardware devices in the service tier of an L3-routed network external to the OpenStack cloud. The F5 OpenStack LBaaS components reside on the Neutron controller in the application layer in the OpenStack cloud.

   BIG-IP "undercloud" deployment

In global routed mode, the |agent-short| automatically uses BIG-IP Local Traffic Manager (LTM) `secure network address translation`_ (SNAT) 'automapping'.
The BIG-IP Local Traffic Manager automatically creates a SNAT pool of existing `self IP`_ addresses.

For incoming traffic, Local Traffic Manager maps the origin IP address to an IP address from the SNAT pool.
This ensures that the server response returns to the client through the BIG-IP system.
For server-initiated traffic, Local Traffic Manager maps the server IP address to an IP address from the SNAT pool, effectively hiding the server's actual IP address from clients.

.. important::

   Because SNAT automap allocates existing self IP addresses into a SNAT pool, you should create enough self IPs to handle anticipated connection loads **before** deploying the |agent-long| in global routed mode. [#snatselfip]_


Next steps
----------

- If this is your initial launch, :ref:`start the F5 agent <topic-start-the-agent>`.
- If you have updated the configurations for a running |agent-short| instance, restart the service:

  - :command:`systemctl systemctl start f5-openstack-agent`   \\ CentOS
  - :command:`service f5-oslbaasv2-agent start`               \\ Ubuntu

See the `F5 Integration for OpenStack`_ documentation for more information.


.. rubric:: Footnotes
.. [#snatselfip] In an :term:`overcloud` deployment, BIG-IP Virtual Edition (VE) may allocate IP addresses automatically.

