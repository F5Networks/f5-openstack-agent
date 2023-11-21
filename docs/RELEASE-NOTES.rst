.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.10.4.2 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
[OPENSTACK-2847] Disable icontrol token authentication by default
[OPENSTACK-2835] modify ManagementRoot

Bug Fixes
`````````

Limitations
```````````

v9.10.4.1 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* [OPENSTACK-2701] hotfix retry to get VLAN mac

Limitations
```````````

v9.10.4 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2701] Update SelfIP port with its vlan MAC
* [OPENSTACK-2766] Use mgmt_ipv6 in some cases
* [OPENSTACK-2751] Support single ipv6 mgmt address
* [OPENSTACK-2766] Update 4 new inventory model
* [OPENSTACK-2764] Adapt to new inventory model
* [OPENSTACK-2766] Modify dev status help msg
* [OPENSTACK-2770] Set connection rate limit division factor 1
* [OPENSTACK-2764] Define use_mgmt_ipv6 option
* [OPENSTACK-2747] Add device status update
* [OPENSTACK-2741] Fetch VLAN Segmentation id via vtep_ip or default
* [OPENSTACK-2701] Enable traffic-group-1 MAC auto configure
* [OPENSTACK-2701] Create or update VIP/SNAT IP/SelfIP with MAC
* [OPENSTACK-2701] Add MAC in interface mapping
* [OPENSTACK-2701] Refactor external interface mapping
* [OPENSTACK-2701] Refactor code to get interface
* [OPENSTACK-2701] Refactor flat network for refactor other code
* [OPENSTACK-2747] Convert to use inventory db
* [OPENSTACK-2694] New monitor process
* [OPENSTACK-2624] Deploy configuration to multiple devices in parallel

Bug Fixes
`````````
* [OPENSTACK-2791] Fix delete healthmonitor even if it is missing
* [OPENSTACK-2741] Fix to choose "default"
* [OPENSTACK-2790] Fix network id
* [OPENSTACK-2780] Fix selfip create, vlan not in route domain
* [OPENSTACK-2751] Input agent conf param when initialize bigip device
* [OPENSTACK-2701] Cannot get length from python None type

Limitations
```````````

v9.10.3 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2697] Make the onboard command line argument format uniform
* [OPENSTACK-2621] Change ACL functions for NG
* [OPENSTACK-2682] add external network mapping for bigip-onboard
* [OPENSTACK-2646] Multi-zone agent

Bug Fixes
`````````
* [OPENSTACK-2624] Fix python 3 error in travis
* [OPENSTACK-2666] fix: create client tcp profile when set keepalive_timeout
* [OPENSTACK-2654] fix bigip-onboard refresh when fail to connect BIG-IP
* [OPENSTACK-2646] Fix rate limit debug log

Limitations
```````````

v9.10.2 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2610] Listener support proxy protocol
* [OPENSTACK-2441] Listener support keepalive_timeout
* [OPENSTACK-2638] Enable iControl token authentication
* [OPENSTACK-2603] Encrypt bigip username and password
* [OPENSTACK-2573] Encode and decode username and password of bigip
* [OPENSTACK-2571] Optimize creating member performance
* [OPENSTACK-2571] Optimize deleting member performance

Bug Fixes
`````````
* [OPENSTACK-2632] Fix when update http2 filtered clientside tcp profile
* [OPENSTACK-2571] Append route domain id to member node name
* [OPENSTACK-2571] Fix member route domain

Limitations
```````````

v9.10.1 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2557] Do not update mac automatically
* [OPENSTACK-2587] Upgrade to python sdk 3.0.11.5
* [OPENSTACK-2557] Clean f5_snat_addresses_per_subnet configuration option
* [OPENSTACK-2557] Clean f5_ha_type configuration
* [OPENSTACK-2557] Clean some configuration options
* [OPENSTACK-2557] Persist configuration periodically
* [OPENSTACK-2557] Update mac and refresh all
* [OPENSTACK-2522] Remove bigip driver init and connection
* [OPENSTACK-2522] Update mac for NG
* [OPENSTACK-2522] Update mac
* [OPENSTACK-2557] Fix resource pending
* [OPENSTACK-2558] Member state collect
* [OPENSTACK-2557] Mac address update
* [OPENSTACK-2558] Collect member stats
* [OPENSTACK-2559] Remove periodic config save
* [OPENSTACK-2559] Remove vlan_binding
* [OPENSTACK-2559] Replace get_all_bigips in network_service.py
* [OPENSTACK-2559] Remove get bigip hosts
* [OPENSTACK-2559] Remove vcmp configuration in l2_service
* [OPENSTACK-2559] Remove get_bigip()
* [OPENSTACK-2559] Remove unused purge_orphaned_nodes to avoid get_bigip()
* [OPENSTACK-2559] Remove vcmp init to avoid calling get_bigip()
* [OPENSTACK-2559] Remove some info of agent configuration
* [OPENSTACK-2557] Adjust bigip-board command
* [OPENSTACK-2559] Remove agent set admin_state_up
* [OPENSTACK-2559] Agent uses driver bigip info to configure bigip
* [OPENSTACK-2559] Purge bigip connection
* [OPENSTACK-2559] Purge periodic-scrub
* [OPENSTACK-2559] Purge periodic-resync
* [OPENSTACK-2559] Purge service sync code
* [OPENSTACK-2559] Purge bigip recover code
* [OPENSTACK-2531] bigip-onboard CLI
* [OPENSTACK-2566] Reserve one floating ip in large snat subnet
* [OPENSTACK-2532] Bump up version number
* [OPENSTACK-2533] Purge ESD
* [OPENSTACK-2533] Remove agent manager

Bug Fixes
`````````
* [OPENSTACK-2587] Ignore 404 for selfip deleting
* [OPENSTACK-2552] Change log level for deleting lbs
* [OPENSTACK-2552] Add snat port NoneType check
* [OPENSTACK-2548] Check unavaliable flavors
* [OPENSTACK-2548] Server check flavor, when client not to do it

Limitations
```````````
