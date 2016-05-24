Agent Configuration File
------------------------

A sample F5® OpenStack agent configuration file is shown below. In your OpenStack cloud, you should install the agent on your Neutron controller and any other host(s) for which you'd like to provision services from BIG-IP®. The file can be found at ``/etc/neutron/services/f5/f5-openstack-agent.ini``.

 When setting up your own F5® agent(s), be sure to use the correct information for your environment.

.. literalinclude:: ../etc/neutron/services/f5/f5-openstack-agent.ini

