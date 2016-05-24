Using the F5® Agent in Neutron LBaaSv2
--------------------------------------

The F5® OpenStack agent can be used to provision BIG-IP® local traffic management (LTM®) services in an OpenStack cloud. It does so via the Neutron LBaaSv2 API, in conjunction with the :ref:`F5® OpenStack LBaaSv2 driver <lbaasv2-driver:home>`.

 When Neutron LBaaSv2 calls are issued to the Neutron controller, the F5® LBaaSv2 driver picks them up and directs them to an F5® agent. The F5® agent starts, and communicates with, a BIG-IP® as determined by the settings in the :ref:`agent configuration file <agent-configuration-file>`. The agent then registers its own named queue, where it receives tasks from the Neutron controller(s). The F5® agent makes callbacks to the F5® drivers to query additional Neutron network, port, and subnet information; allocate Neutron objects (for example, fixed IP addresses); and report provisioning and pool status.

