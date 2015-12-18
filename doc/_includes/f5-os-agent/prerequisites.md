- Download the F5 OpenStack Plug-in package from [F5's DevCentral](https://devcentral.f5.com/d/openstack-neutron-lbaas-driver-and-agent).

- Install the [F5 LBaaS Plug-in Driver]({{ f5-os-lbaasv1/index.html | prepend: site.url }}) before you deploy the Agent. 
  
- Set up at least one BIG-IP cluster - or, 'device service group \(DSG\)' -  before you deploy the Agent. You'll need administrator access to the BIG-IP and all cluster members to do so.

**Tip:** Make note of the IP addresses and credentials for the devices in the cluster; you'll need to enter them in the Agent config file\(s\).

- Agent config file\(s\) \([see Table 1](f5-os-agent/os_lbaas_agent_config_settings.xlsx)\). The installation will create a default config file, but you'll need to manually create a separate file for each Agent you deploy. 
