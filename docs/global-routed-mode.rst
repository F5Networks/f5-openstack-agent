.. _global-routed-setup:

.. index::
   single: f5-openstack-agent; global routed mode

Run the F5 Agent in global routed mode
======================================

Global routed mode lets you use BIG-IP device(s) as edge load balancer(s) for your OpenStack cloud.
This mode generally applies to BIG-IP device(s) that have an L2 connection to the OpenStack external provider network.
Because all tenants are in the BIG-IP global route domain (``rd0``),

- global routed mode doesn't support Neutron tenant isolation, and
- the |agent-long| assumes that all L3 virtual IP addresses are globally routable.

Global routed mode uses BIG-IP Local Traffic Manager (LTM) `secure network address translation`_ (SNAT) 'automapping' to route traffic for OpenStack Neutron tenants.

- For incoming traffic, LTM maps the origin IP address to an IP address from the SNAT pool, ensuring the server response returns to the client through the BIG-IP system.
- For server-initiated traffic, LTM maps the server's IP address to an IP address from the SNAT pool.

.. important::

   SNAT automap allocates existing self IP addresses into a SNAT pool.
   Be sure to create enough self IPs to handle anticipated connection loads **before** deploying the |agent-short| in global routed mode. [#snatselfip]_

Set-up
------

.. important::

   The |agent-short| cannot read existing BIG-IP configurations or non-Neutron network configurations.
   Be sure to set up the configuration file to correctly reflect the existing network architecture and the BIG-IP system configurations.


.. include:: /_static/reuse/edit-agent-config-file.rst

#. Set the desired |agent-short| configuration parameter(s).
   The example below represents the settings used in the |agent-short| functional tests.

   .. literalinclude:: /_static/config_examples/f5-openstack-agent.grm.ini

   :fonticon:`fa fa-download` :download:`Download the example configuration file </_static/config_examples/f5-openstack-agent.grm.ini>`

#. Restart the |agent-short| service.

   .. include:: /_static/reuse/restart-f5-agent.rst

What's Next
-----------

See `F5 Agent modes`_ for detailed information regarding each of the Agent's modes of operation and example use cases.

.. rubric:: Footnotes
.. [#snatselfip] In an :term:`overcloud` deployment, BIG-IP Virtual Edition (VE) may allocate IP addresses automatically.

