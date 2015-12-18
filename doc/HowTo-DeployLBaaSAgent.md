---
layout: docs_page
title: How to Deploy the F5 LBaaS Agent in OpenStack
resource: true
openstack_version:   
---

#How to Deploy the F5 LBaaS Agent in OpenStack

## Overview
This guide will help you set up load-balancing as a service (LBaaS) in OpenStack using the F5 LBaaS Plug-in. Deploying the F5 LBaaS Plug-in and Agent in an OpenStack distribution allows you to provision virtual IPs, server pools, health monitors, and load balancing on your hardware or Virtual Edition BIG-IP.

### Prerequisites

- Download the F5 OpenStack Plug-in package from [F5's DevCentral](https://devcentral.f5.com/d/openstack-neutron-lbaas-driver-and-agent).

- Install the [F5 LBaaS Plug-in Driver]({{ f5-os-lbaasv1/index.html | prepend: site.url }}) before you deploy the Agent. 
  
- Set up at least one BIG-IP cluster - or, 'device service group \(DSG\)' -  before you deploy the Agent. You'll need administrator access to the BIG-IP and all cluster members to do so.

**Tip:** Make note of the IP addresses and credentials for the devices in the cluster; you'll need to enter them in the Agent config file\(s\).

- Agent config file\(s\) \([see Table 1](f5-os-agent/os_lbaas_agent_config_settings.xlsx)\). The installation will create a default config file, but you'll need to manually create a separate file for each Agent you deploy. 

### Placement

The F5 LBaaS Agent can run on any host that has the Neutron python libraries installed. We recommend using a Neutron Controller or Gateway node, as they contain the appropriate libraries by default. You can also run the agent on a dedicated node. 

We also recommend running multiple F5 LBaaS agents for the same environment simultaneously on different hosts. Doing so provides some redundancy in LBaaS provisioning for that environment. 

**Note:** If you choose to deploy multiple agents for the same environment, they *must* run on different hosts. 

You can run multiple F5 LBaaS agents simultaneously on the same host, but they must be orchestrating different environments \(in other words, different TMOS clusters with unique environment prefixes\). 

## Install the Agent

Use the command set for your distribution to install the Neutron Gateway Packages for the F5 LBaaS Agent.

### Ubuntu:

`dpkg -i f5-bigip-lbaas-agent_1.1.0-1_all.deb`

### Red Hat/CentOS:

`rpm -i f5-bigip-lbaas-agent-1.1.0-1.noarch.rpm`

**NOTE:** The actual file names will vary from version to version.

## Stop the Agent

The agent launches automatically on install; since it hasn't been configured yet, **run the appropriate command for your distro to stop the process**: 

### Ubuntu
`service f5-bigip-lbaas-agent stop`

### RedHat / CentOS
`service f5-bigip-lbaas-agent stop`

## Installing Additional Agents

Complete both of the installation steps \(install, then stop\) on each host on which you want the F5 LBaaS Agent to run.

## Set up the Agent

The agent configuration settings are found in */etc/neutron/f5-bigip-lbaas-agent.ini*. \(Figure 1\) is a sample config file which shows the available options.

![Table 1. F5 OpenStack Agent Configuration Options](f5-os-agent/os_lbaas_agent_config_settings.xlsx) 

## Start the Agent

**NOTE:** If you want to start with clean logs, you should remove the log file first: 
`rm /var/log/neutron/f5-bigip-lbaas-agent.log`

### Ubuntu
To start the agent, run 
`service f5-bigip-lbaas-agent start`

### Red Hat / CentOS
To start the agent, run 
`service f5-bigip-lbaas-agent start`

## Check the Agent Status

### Ubuntu
To check the Agent's status, run 
`neutron agent-list`

### Red Hat / CentOS
To check the Agent's status, run 
`neutron agent-list`

![Figure 1. Neutron Agent Status List](f5-os-agent/assets/lbaas-agent-status.png "Figure 1")

**NOTE:** It may take a few seconds for the agent to appear in the status list (shown in Figure 1) after restarting. If the agent does not start properly, an error will be logged in */var/log/neutron/f5-bigip-lbaas-agent.log*.

## Enable LBaaS in OpenStack GUI

Go to the OpenStack cloud controller node.
 
In the 'local\_settings' file, set  'enable\_lb'  to "True", as shown below.

`OPENSTACK_NEUTRON_NETWORK = { 'enable_lb': True, ...}"` -- \[THIS NEEDS VERIFICATION AND OPENSTACK VERSIONING --JP\]

## Restart the web server to make the setting take effect:

### Ubuntu
To restart the web server, run
`service apache2 restart`

### Red Hat / CentOS
To restart the web server, run
`service httpd restart`

## Additional Information

### Tenant Scheduler
The F5 LBaaS Plug-in uses a scheduler which, by default, associates all LBaaS pools on the same cluster with the same tenant. This association is maintained in the OpenStack database. To view the associations: 
    
1. Run `neutron agent-list`. 
2. Run `neutron lb-pool-list-on-agent <agent-id>` for each LBaaS agent.

If you add more agent-cluster groups, the LBaaS plug-in will automatically identify which agent it should talk to in order to service a given tenant. 

**NOTE:** If you delete all pools for a tenant, the record of how to map the tenant pool to an agent is also deleted. In such cases, the BIG-IP may choose a new agent for that tenant.
