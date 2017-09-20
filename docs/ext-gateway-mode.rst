.. index::
   single: F5 Agent; External gateway mode

.. _external-gateway-setup:

.. sidebar:: :fonticon:`fa fa-exclamation-triangle` Compatibility notice:

   **External gateway mode** and **common networks** are not available in OpenStack Liberty deployments.

Run the F5 agent in external gateway mode
=========================================

External gateway mode lets you route external port addresses that aren't orchestrated by Neutron to ports inside the OpenStack cloud.
When running in external gateway mode, the |agent-long| creates routes between tenant subnets and external port addresses on the BIG-IP system.

.. warning::

   - This mode requires a router outside of the OpenStack cloud to provide routes for external traffic.
   - Using the |agent-short| in external gateway mode with :code:`f5_common_networks = False` is  not supported.
   - Using the |agent-short| with Neutron RBAC is not supported.

Set-up
------

.. note::

   Using external gateway mode requires the use of `common networks </cloud/openstack/latest/lbaas/manage-common-net-objects.rst>`_.

   Whether you're installing the |agent-short| for the first time or updating an existing agent-short, turning on common networks has the same effect.
   After the |agent-short| restarts, it reads information about the network from the Neutron database and populates objects in the BIG-IP :code:`/Common` partition accordingly.

.. _fresh install ext-gateway:

Fresh installation
``````````````````

If this is your first time setting up the |agent-short| in OpenStack:

.. include:: /_static/reuse/install-agent-driver_edit-config.rst

#. Set the desired |agent-short| configuration parameter(s).

   ::

     external_gateway_mode = True
     f5_common_networks = True

#. Restart the |agent-short| service.

   .. include:: /_static/reuse/restart-f5-agent.rst


Update an existing F5 agent
```````````````````````````

To update the configuration for an |agent-short| that's already running:

#. Stop the |agent-short| service.

   .. include:: /_static/reuse/stop-the-agent.rst

#. Use the built-in |agent-short| cleanup utility to clear each BIG-IP partition associated with a Neutron loadbalancer managed by the Agent instance.

   - Pass in the name of the partition as the :code:`--partition` argument.
   - Provide the correct path and filename for your |agent-short| configuration file. [#filename]_

     .. code-block:: console

        python ./f5-openstack-agent/utils/clean_partition.py \\
        --config-file /etc/neutron/services/f5/f5-openstack-agent.ini \\
        --partition Test_openstack-lb1

#. Complete steps 3-5 in the :ref:`Fresh installation <fresh install ext-gateway>` section.

   - Edit the :ref:`F5 Agent configuration file`.
   - Set :code:`external_gateway_mode` and :code:`f5_common_networks` to True.
   - Restart the |agent-short|.

What's Next
-----------

See `F5 Agent modes`_ for detailed information regarding each of the Agent's modes of operation and example use cases.

.. :ref:`Create and delete LTM objects with common network resources`
.. :ref:`Create and delete SNAT pools with a common network listener`

.. rubric:: Footnotes
.. [#filename] The name of your configuration file may be different if you're running multiple |agent| instances in `Differentiated service environments`_.
