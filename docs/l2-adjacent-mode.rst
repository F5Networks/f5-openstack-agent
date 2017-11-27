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

#. Restart the |agent-short| service.

   .. include:: /_static/reuse/restart-f5-agent.rst


What's Next
-----------

- See `F5 Agent modes`_ for detailed information regarding each of the Agent's modes of operation and example use cases.
- See `How to set up the F5 Agent for Hierarchical Port Binding </cloud/openstack/v1/lbaas/set-up-agent-hpb.html>`_ for information about standard and Cisco ACI HPB deployments.

.. todo:: add Cisco APIC/ACI deployment solution guide and link to it here

