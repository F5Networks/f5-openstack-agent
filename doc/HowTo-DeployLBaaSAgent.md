How to Deploy the F5 LBaaS Agent in OpenStack
------------------------

#Overview
Use the information in this guide to deploy the F5 LBaaS Agent in your OpenStack cloud.

#Prerequisites

You must [deploy the F5 LBaaS Plug-in](HowTo-DeployLBaaSPlugin.md) before you deploy the agent. 

You must have at least one BIG-IP cluster, or 'device service group \(DSG\)' set up before you deply the agent. 

**Tip:** Make note of the IP addresses and credentials for the devices in the cluster; you'll need to enter them in the agent's config file. 

# Agent Installation

##Placement

You can run the F5 LBaaS agent on any host that has the Neutron python libraries installed. We recommed using a Neutron Controller or Gateway node, as they contain the appropriate libraries by default. You can also choose to run the agent on a dedicated node. You can run multiple F5 LBaaS agents on the same host simultaneously.

## 1. Install Neutron Gateway Packages

First, install the F5 LBaaS agent on the server. 

### Ubuntu:

`dpkg -i f5-bigip-lbaas-agent\_1.1.0-1\_all.deb`

### Red Hat/Centos:

`rpm -i f5-bigip-lbaas-agent-1.1.0-1.noarch.rpm`

**NOTE:** The actual file names may vary from version to version.

## 2. Stop the Agent

The agent launches automatically on install; since it hasn't been configured yet, **run the command below to stop the process**: 

`service f5-bigip-lbaas-agent stop`

To remove any error messages logged while the process ran, use the command `rm /var/log/neutron/f5-bigip-lbaas-agent.log`.

### Install Additional Agents

You can run multiple F5 LBaaS agents - and, therefore, multiple clusters - simultaneously. If you wish to install additional agents on separate hosts, do so now. Be sure to complete both of the above steps \(install, then stop\) for each additional agent.

## 3. Set up the Agent

The agent configuration settings are found in the file */etc/neutron/f5-bigip-lbaas-agent.ini*. A sample configuration file \(Figure 1\) explains the various available settings.

[View Figure 1 (PDF)](lbaas-agent-config-sample.pdf) 

## 4. Start the Agent

**NOTE:** If you want to start with clean logs, you should remove the log file first: `rm /var/log/neutron/f5-bigip-lbaas-agent.log`

Enter the following command to restart the agent:

`service f5-bigip-lbaas-agent restart`

# Check the Agent Status

Run the below command to check the agent status. 
`manager@maas-ctrl-4:\~\$ neutron agent-list`

**NOTE:** You may need to wait a few seconds after restarting the agent before it appears the list as shown in Figure 2.

![](lbaas-agent-status.png "Figure 2")

If the agent does not start properly, an error will be logged in
the file */var/log/neutron/f5-bigip-lbaas-agent.log*.

# Enable LBaaS GUI in OpenStack

1. Go to the OpenStack cloud controller node.
2. In the 'local\_settings' file, change the 'enable\_lb' option to True.

The syntax will be something like the following:

"OPENSTACK\_NEUTRON\_NETWORK = { 'enable\_lb': True, ...}""

3. Restart the web server for the setting to take effect:
    `service httpd restart`


# Additional Information

## Tenant Scheduler

The F5 LBaaS Plug-in uses a scheduler which, by default, associates
all LBaaS pools with the same tenant on the same cluster. This association is maintained in the OpenStack database. 

To view the associations: 
    1. Run the command `neutron agent-list`. 
    2. Run `neutron lb-pool-list-on-agent &lt;agent-id&gt;` for each LBaaS agent.

If you add more agent-cluster groups, the LBaaS plug-in will automatically identify which agent it should talk to in order to service a given tenant. 

**NOTE:** If you delete all pools for a tenant, the record of how to map the tenant pool to an agent is also deleted. In such cases, the BIG-IP may choose a new agent for that tenant.
