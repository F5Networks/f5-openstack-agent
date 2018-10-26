.. _l2-adjacent-setup:

.. index::
   single: f5-openstack-agent; L2-adjacent mode

Run the F5 Agent in L2-adjacent mode
====================================

L2-adjacent mode lets you use BIG-IP device(s) deployed in micro-segmentation architectures that require L2 and L3 routing, including software-defined networks (SDN).

L2-adjacent mode is the **default mode of operation** for the |agent-short|.

.. important::

   - Set up all Neutron and external network components before you deploy the |agent-short| in L2-adjacent mode.

   - This mode of deployment may require a BIG-IP `Better or Best license`_ that supports SDN.

.. warning::

   Many L3 segmentation mode parameters depend on other configuration parameters.
   Read about the :ref:`F5 agent configuration parameters <agent-config-parameters>` before changing these settings to ensure they don't conflict.

**L2 Population Service**

The F5 LBaaS agent supports the OpenStack Neutron ML2 population service. When you enable L2 population, the agent registers for Neutron L2 population updates and populates tunnel FDB entries in your BIG-IP device. When you place VIPs on tenant overlay networks, the F5 LBaaS agent sends tunnel update messages to the Open vSwitch agents, informing them of TMOS device VTEPs. This enables tenant guest virtual machines or network node services to interact with the TMOS provisioned VIPs across overlay networks. The F5 LBaaS Agent reports the BIG-IP VTEP addresses stored in its configuration to Neutron.

Enable L2 population if you intend to migrate pool members to different virtual machines without re-creating your load balancer configuration. Pool member migration won't function properly if L2 population isn't enabled.

With L2 population enabled, the F5 agent can also create static ARP entries on the BIG-IP device(s). This eliminates the need for the BIG-IP device to use ARP broadcast (flooding) across tunnels to learn the location of pool members.

.. note::

   You can set the F5 Agent to create Static ARP entries for BIG-IP devices running version 12.x or later. 

Set-up
------

.. important::

   The |agent-short| cannot read existing BIG-IP configurations or non-Neutron network configurations.
   Be sure to set up the configuration file to correctly reflect the existing network architecture and the BIG-IP system configurations.


.. include:: /_static/reuse/edit-agent-config-file.rst

#. Set the desired |agent-short| configuration parameter(s).
   The example below represents the settings used in the |agent-short| functional tests.

   .. literalinclude:: /_static/config_examples/f5-openstack-agent.vxlan.ini

   \

   :fonticon:`fa fa-download` :download:`Download the example configuration file </_static/config_examples/f5-openstack-agent.vxlan.ini>`

   .. tip:: To enable L2 population and static ARP (optional), use the settings shown below.

      .. code-block:: text

         #
         f5_populate_static_arp = True
         #
         l2_population = True
         #



#. Restart the |agent-short| service.

   .. include:: /_static/reuse/restart-f5-agent.rst


What's Next
-----------

- See `F5 Agent modes`_ for detailed information regarding each of the Agent's modes of operation and example use cases.
- See `How to set up the F5 Agent for Hierarchical Port Binding`_ for information about standard and Cisco ACI HPB deployments.

.. todo:: add Cisco APIC/ACI deployment solution guide and link to it here

