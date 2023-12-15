.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.10.6.1 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2905] New implementation of flavor 1-6 SNAT
* [OPENSTACK-2934] Delete server side profile created by previous TOA implementation
* [OPENSTACK-2905] Rebuild compatibility for legacy SNAT style
* [OPENSTACK-2936] Update LB flavor in a new manner

Bug Fixes
`````````
* [OPENSTACK-2939] Ignore 400 error of deleting route domain when concurrent deleting lb

Limitations
```````````

v9.10.6 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
*  [OPENSTACK-2890] Suppress vlan 409 error log
*  [OPENSTACK-2915] New implementation of flavor 21
*  [OPENSTACK-2915] Always create snat subnet with 128 size
*  [OPENSTACK-2930] Raise exception if all bigips offline
*  [OPENSTACK-2890] Retry 30 times when 401 or device busy happens
*  [OPENSTACK-2890] 400 retry for device or resource busy
*  [OPENSTACK-2890] 401 retry for loading nodes
*  [OPENSTACK-2912] Not append if profile already exists
*  [OPENSTACK-2912] Add sip profile manipulation
*  [OPENSTACK-2912] remove old description way
*  [OPENSTACK-2899] SIP VS
*  [OPENSTACK-2900] remove useless comment
*  [OPENSTACK-2908] remove 'multiple' code for member create/delete
*  [OPENSTACK-2908] remove useless arguement for prep_mb_network.
*  [OPENSTACK-2911] create and update description with empty
*  [OPENSTACK-2910] Listener support rewrite_xff.
*  [OPENSTACK-2900] add bulk member create/delete
*  [OPENSTACK-2898] Restore os_password AES decryption code
*  [OPENSTACK-2787] Occupy device
*  [OPENSTACK-2879] Remove redundant loading selfip action
*  [OPENSTACK-2879] Remove redundant deleting route domain action
*  [OPENSTACK-2863] Update travis deploy condition.
*  [OPENSTACK-2863] Remove 9.9 and 9.8 release notes.
*  [OPENSTACK-2863] Update documentation deploy to compatible with 4-digit version numbers.
*  [OPENSTACK-2901] Add source ip port persistence support.
*  [OPENSTACK-2787] Enqueue provisioning job at the very beginning
*  [OPENSTACK-2894] remove bigip decription for vip, vs, pool, healthmonitor
*  [OPENSTACK-2900] remove pool_port_<member-id>
*  [OPENSTACK-2875] new way to delete in _remove_tenant_replication_mode
*  [OPENSTACK-2840] create all the members of a pool at once
*  [OPENSTACK-2840] Do not overwrite existing http2 profile.
*  [OPENSTACK-2873] Retry 401 when adding vlan to route domain
*  [OPENSTACK-2873] Retry 401 when adding vlan interfaces
*  [OPENSTACK-2840] remove the useless subnet argument.
*  [OPENSTACK-2858] Reduce iControl calls when deleting LB
*  [OPENSTACK-2858] Reduce iControl calls for LB creation
*  [OPENSTACK-2840] rebuild lb tree inplace.
*  [OPENSTACK-2858] Do not print exception of ignored HTTP errors
*  [OPENSTACK-2865] enable acl rebuild function
*  [OPENSTACK-2866] Remove obsolete inventory code.
*  [OPENSTACK-2859] Remove obsolete code (lbaas builder)
*  [OPENSTACK-2868] add password_cipher_mode back
*  [OPENSTACK-2792] modify l2 part and remove f5os configs
*  [OPENSTACK-2720] add f5os and l2 related logic
*  [OPENSTACK-2720] remove password_cipher_mode
*  [OPENSTACK-2720] ng F5OS rSeries
*  [OPENSTACK-2860] Remove TOA irule log.
*  [OPENSTACK-2840] rebuild l7policies and l7rules
*  [OPENSTACK-2840] rebuild healthmonitor for a pool
*  [OPENSTACK-2840] rebuild pool
*  [OPENSTACK-2840] add rebuild member function
*  [OPENSTACK-2840] declare rd_id as None
*  [OPENSTACK-2840] fix vxlan update fdb for rebuild
*  [OPENSTACK-2860] TOA tcp option setting for IPv4 and IPv6 separately and add port number.
*  [OPENSTACK-2859] Ignore icontrol 409 by default when creating resource
*  [OPENSTACK-2847] Retry 401 when cleanup partition
*  [OPENSTACK-2847] Retry 401 when initialize bigip connection
*  [OPENSTACK-2840] rebuild change for agent

Bug Fixes
`````````
*  [OPENSTACK-2905] Lock route domain when inserting vlan
*  [OPENSTACK-2905] Don't handle vlan not in rd error when creating selfip
*  [OPENSTACK-2879] Only delete empty route domain
*  [OPENSTACK-2886] Fix TOA profile, only create client side tcp profile.
*  [OPENSTACK-2867] Fix creating route domain racing problem
*  [OPENSTACK-2867] Fix creating vlan racing problem
*  [OPENSTACK-2867] Needn't to detach redirect policy after removing vs
*  [OPENSTACK-2861] selfip not deleted

Limitations
```````````

v9.10.5 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2847] Refactor network helper
* [OPENSTACK-2847] Refactor resource manager
* [OPENSTACK-2847] Refactor icontrol driver
* [OPENSTACK-2847] Refactor selfip
* [OPENSTACK-2847] Refactor system helper
* [OPENSTACK-2847] Retry when icontrol return 401
* [OPENSTACK-2847] Disable icontrol token authentication by default (9.10)
* [OPENSTACK-2835] Modify ManagementRoot
* [OPENSTACK-2848] Update f5_bandwidth_max to 120000 to support flavor 21
* [OPENSTACK-2754] Support flavor 21
* [OPENSTACK-2784] No ssl 3.0
* [OPENSTACK-2782] Add access_log logic feat

Bug Fixes
`````````
* [OPENSTACK-2855] Check if route exist, before create route
* [OPENSTACK-2807] Fix requested VLAN not found
* [OPENSTACK-2701] Fix retry to get VLAN mac
* [OPENSTACK-2807] Fix snatpool partition was wrong
* [OPENSTACK-2806] Save lb_netinfo in service instead of NetworkServiceBuilder to avoid race condition when parallel deploy configuration to multi device.

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
