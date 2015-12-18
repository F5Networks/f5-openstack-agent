Go to the OpenStack cloud controller node.
 
In the 'local\_settings' file, set  'enable\_lb'  to "True", as shown below.

`OPENSTACK_NEUTRON_NETWORK = { 'enable_lb': True, ...}"`