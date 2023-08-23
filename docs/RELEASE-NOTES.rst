.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.10.5.1 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2860] TOA tcp option setting for IPv4 and IPv6 separately and add port number.
* [OPENSTACK-2860] Remove TOA irule log.

Bug Fixes
`````````
* [OPENSTACK-2861] Fix to delete selfip
* [OPENSTACK-2847] Retry 401 when initialize bigip connection
* [OPENSTACK-2847] Retry 401 when cleanup partition
* [OPENSTACK-2859] Ignore icontrol 409 by default when creating resource

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

v9.9.54 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

* [OPENSTACK-2514] vip connection limit
* [OPENSTACK-2516] Include LTM license in agent configuration
* [OPENSTACK-2500] Support large SNAT pool

Bug Fixes
`````````

* [OPENSTACK-2513] fix ipv6 connection rate limit

Limitations
```````````

v9.9.53 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

* [OPENSTACK-2512] Include VTEP IP address in Neutron port

Bug Fixes
`````````

Limitations
```````````

v9.9.52 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

* [OPENSTACK-2490] Support flavor 11-13

Bug Fixes
`````````

Limitations
```````````

v9.9.51 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* [OPENSTACK-2482] delete cafile for mtls profile.

Limitations
```````````

v9.9.50 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2406] Disable ESD refresh job
* [OPENSTACK-2426] Flavor snatpool function
* [OPENSTACK-2426] Dual stack and flavour SNAT with one Netron Port
* [OPENSTACK-2440] Enable ftp, https TOA
* [OPENSTACK-2440] Change https listener to standard model
* [OPENSTACK-2426] Remove member config snat ip
* [OPENSTACK-2474] Change port number
* [OPENSTACK-2482] Remove certs and keys as removing ssl profiles
* [OPENSTACK-2479] Dual-stack-snat
* [OPENSTACK-2479] Change member and add route
* [OPENSTACK-2381] Only update interval from api side
* [OPENSTACK-2425] Per dest addr

Bug Fixes
`````````
* [OPENSTACK-2483] Fix confusing logs to avoid misunderstanding.

Limitations
```````````

v9.9.40.patch2 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2284] refact: create route domain/vlan by net
* [OPENSTACK-2344] feat: use '--transparent' to enable/disable xff
* [OPENSTACK-2344] chore: remove xff configuration in json file

Bug Fixes
`````````
* [OPENSTACK-2262] Fix IPv6 redirect host parsing

Limitations
```````````

v9.9.40.patch1 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2343] Support uppercase cipher policy name
* [OPENSTACK-2083] Add TOA feature
* [OPENSTACK-2083] Remove pervious tranparent function
* [OPENSTACK-2325] Add cipher policy config file
* [OPENSTACK-2262] Support redirect LTM policy
* [OPENSTACK-2325] Enable TLS cipher suites policy definition
* [OPENSTACK-2277] Add a periodic config save task

Bug Fixes
`````````
* [OPENSTACK-2282] Fix snat creation conflict issue
* [OPENSTACK-2342] Fix: selfip recreating unabled to catch HTTP 409
* [OPENSTACK-2295] Ensure route domain id consistency
* [OPENSTACK-2294] Fix: multiple agents updating snatpool member causes
* [OPENSTACK-2341] Fix: get all nodes in a partition
* [OPENSTACK-2253] Ensure source ip session persistence when lb algorithm is SOURCE_IP

Limitations
```````````

v9.9.40 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Identify customized http profile
* Add the profile's context when trying to update the listener's profiles to avoid conflict.
* Enable tls+http2 profile support

Bug Fixes
`````````
* Fix TLS1.3 cipher group
* Fix the variable name conflicts with the input parameter.
* Use the full path name when creating a new profile.

Limitations
```````````

v9.9.31 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* New way for health monitor timeout
* Add udp sip diameter hm type
* Support http2 profile
* Support websocket profile
* Add disable option for HTTP2 and Websocket

Bug Fixes
`````````
* Avoid patching profile failure, if profile is not created
* If members exist, it will cause HTTP 409 ERROR
* Update profiles before retriving the profiles from bigip.
* Add rule and remove rule for ACLGroup

Limitations
```````````

v9.9.30 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Add flavor support: connection limit and connection rate limit.
* Bind logging profile to http/terminated_https vs.
* Add checking status support and don't send the members with status of none or checking.
* Add ACL feature.
* Support cipher options.

Enhancement
```````````

Limitations
```````````

v9.9.6 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Revert the logging profile at this moment.

Bug Fixes
`````````

Limitations
```````````

v9.9.5 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* Catch all exception for route domain creation.
* Fix the issue of deleting nodes and snat in bigip ha mode.

Limitations
```````````

v9.9.4 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* Fix check nodes issue in current partition

Limitations
```````````

v9.9.3 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* use the pool-id address and port to update the port
* multiple agents update the members in order

Bug Fixes
`````````
* Fix the issue of route domain issue: id already exists
* change the member update status interval configurable
* convert bandwidth from string to int
* Fix the KeyError issue caused by heartbeat periodic task.
* Fix negative periodic value not taking effect
* by default disable the scrub agent task
* Fix rds cache polluted problem
* Cleanup all snat, vlan and self ip before removing partition
* Handle bigip status check

Limitations
```````````

v9.9.2 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Login docker hub with an id under f5devcentral org
* Handle both None and '' situations for listener['customized']
* Ensure to overwrite persistence profile
* Tolerate persistence timeout in string type
* Change the algorithm from least-connection-node to least-connection-member for source_ip algorithm in neutorn
* Use HEAD or GET for monitor
* Remove persist profile from vs, if its default pool remove persistence
* When update listener with customized paramater then bind the new http profile to the listener
* Will not del the vs customized property. Use it when configuring the other bigips in cluster mode.
* use a new way to check if tls and customized properties change.

Bug Fixes
`````````
* Fix customized bug
* Fix 'error opening BIG-IP - active:BIG-IP ready for provisioning'

Limitations
```````````

v9.9.1 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Support session persistence timeout parameter in API
* Customerised timeout value in persistence iRule and tolerate negative or None value of persistence_timeout
* Add '--customized' support for listener creation
* Add to configure options for sanity check for bwc
* Add the max bandwidth is 10000MB instead of 1000MB for bwc
* Change icontrol heartbeat interval as same as _report_state
* Support to modify lb operating_status accordingly

Bug Fixes
`````````
* Do not detach user defined persist profile when removing pool
* Fix listener exception log
* Fix member batch deletion breakdown
* Throw exception if no active bigips
* Fix backwards compatibility problem of SNAT pool member name

Limitations
```````````

v9.9.0 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Support to create listener with client ca certificate.
* Support create/delete/update the irule profile and bwc policy dynamically when creating/deleting a loadbalancer.
* Remove the previous bwc function.

Bug Fixes
`````````

Limitations
```````````

v9.8.40 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* protocol 0 support
* listener tls support

Bug Fixes
`````````
* Fix operating status issue
* fix http profile issue

Limitations
```````````

v9.8.21 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* Remove unnecessary dependency package

Limitations
```````````

v9.8.20 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Support L7Policy and L7Rule in Agent lite mode
* Support FTP and TERMINATED_HTTPS protocol in Agent lite mode
* Support to create VS specific http profile, cookie persistence profile and source_addr persistence profile

Bug Fixes
`````````
* Fix HA sync bug in L2 network mode

Limitations
```````````

v9.8.19 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Create virtual server specific http_cookie and source_addr persistence profile

Bug Fixes
`````````
* Improve the performance of route domain and partition cleanup

Limitations
```````````

v9.8.18 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Add a 'lite' mode for F5 OpenStack Agent, which can improve the performance to deploy BIG-IP configuration and also tolerate some of the manual configuration changes made by user in BIG-IP.

Bug Fixes
`````````
* Route domain and partition deleted while deleting loadbalancer.

Limitations
```````````
* Agent lite only works with F5 LBaaS driver whose performance mode is 3.

v9.8.6 (Mitaka, Newton, Ocata, Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Mitaka, Newton, Ocata, Pike and Queens Openstack releases.

Added Functionality
```````````````````
* snat transparent and udp
* bandwidth control
* diameter, SIP

Bug Fixes
`````````

Limitations
```````````

v9.8.3 (Mitaka, Newton, Ocata, Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Mitaka, Newton, Ocata, Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Refresh esd with trigger

Bug Fixes
`````````

Limitations
```````````

v9.8.2 (Mitaka, Newton, Ocata, Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Mitaka, Newton, Ocata, Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Enhanced Advanced Load Balancer(ALB).

  - Added a switch to control whether or not b64decode 2 passwords

Bug Fixes
`````````

Limitations
```````````

v9.8.1 (Mitaka, Newton, Ocata, Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Mitaka, Newton, Ocata, Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Enhanced Advanced Load Balancer(ALB).

  - Added support for Queens
  - Added some HPB code
  - Enabled REGEX comparison type for l7 rules
  - Added some IPv6 code


Bug Fixes
`````````

Limitations
```````````

v9.8.0 (Mitaka, Newton, Ocata, Pike)
------------------------------------
NOTE: This version of F5 Openstack Agent will support Mitaka, Newton, Ocata and Pike Openstack releases.

Added Functionality
```````````````````
* Enhanced Advanced Load Balancer(ALB).

  Add 2 profile types support in Enhanced Service Definition(ESD):

  - HTTP profile.
  - OneConnect profile.

Bug Fixes
`````````
- Can not create selfip in both units using the same route domain ids.
- Deletes incorrect route domain.

Limitations
```````````
