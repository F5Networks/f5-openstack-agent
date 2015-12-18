---
layout: docs_page
title: How to Deploy the F5 LBaaS Agent in OpenStack
tags: agent, lbaas, openstack
resource: true
openstack version: 
---

#How to Deploy the F5 LBaaS Agent in OpenStack

## Overview

{% include f5-os-agent/overview.md %}

### Prerequisites

{% include f5-os-agent/prerequisites.md %}

### Placement

{% include f5-os-agent/agent_placement.md %}

## Install the F5 OpenStack LBaaS Plug-in Agent

Use the command set for your distribution to install the Neutron Gateway Packages for the F5 LBaaS Agent.

{% include f5-os-agent/install_agent_ubuntu.md %}

{% include f5-os-agent/install_agent_redhat-centos.md %}

{% include f5-os-agent/install_agent_note.md %}

## Stop the Agent

{% include f5-os-agent/install_agent_stop_ubuntu-redhat-centos.md %}

## Installing Additional Agents

Complete both of the installation steps \(install, then stop\) on each host on which you want the F5 LBaaS Agent to run.

## Set up the Agent

{% include f5-os-agent/install_agent_setup.md %}

Table 1.
{% include f5-os-agent/os_lbaas_agent_config_settings.md %}

## Start the Agent

{% include f5-os-agent/install_agent_start_note.md %}

{% include f5-os-agent/install_agent_start_ubuntu-redhat-centos.md %}

## Check the Agent Status

{% include f5-os-agent/install_agent_status_ubuntu-redhat-centos.md %}

Figure 1. 
{% include f5-os-agent/assets/lbaas-agent-status.png %}

{% include f5-os-agent/install_agent_check_status_note.md %}

## Enable LBaaS in OpenStack GUI

{% include f5-os-agent/install_agent_enable_lbaas.md %}

## Restart the web server to make the setting take effect:

{% include f5-os-agent/install_agent_restart_webserver_ubuntu.md %}

{% include f5-os-agent/install_agent_restart_webserver_redhat-centos.md %}

## Additional Information

{% include f5-os-agent/f5-lbaasv1-plugin_tenant-scheduler.md %}

