.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.8.50(Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2671] Encode confd password
* [OPENSTACK-2671] Skip to init confd client if no confd address
* [OPENSTACK-2644] Search VE tenant in F5OS by BIG-IP mgmt ip
* [OPENSTACK-2644] Deploy configuration to BIG-IP HA pair on rSeries
* [OPENSTACK-2644] Create/delete vlan via F5OS
* [OPENSTACK-2644] Use PUT instead of PATCH to associate the first vlan
* [OPENSTACK-2644] Implement restconf client
* [OPENSTACK-2644] Define F5OS configuration
* [OPENSTACK-2474] Support to change port number

Bug Fixes
`````````
* [OPENSTACK-2671] Change agent admin_state_up to false if exception is raised during device init
* [OPENSTACK-2482] Delete cafile for mtls profile.
* [OPENSTACK-2482] Remove certs and keys as removing ssl profiles.
* [OPENSTACK-2483] Fix confusing logs to avoid misunderstanding.

Limitations
```````````

v9.8.49(Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2406] Disable ESD refresh job
* [OPENSTACK-2440] Enable toa function for FTP and HTTPS
* [OPENSTACK-2459] Let --transparent and --customize control XFF function

Bug Fixes
`````````

Limitations
```````````

v9.8.48 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* [OPENSTACK-2381] Only update interval from api side

Limitations
```````````

v9.8.48beta (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2350] depercated customized to configure xff
* [OPENSTACK-2350] feat: disable --customized to update xff
* [OPENSTACK-2350] refact: refactory XFF function to use transparent
* [OPENSTACK-2350] feat: add TOA funtion for TCP listener
* [OPENSTACK-2349] Support redirect LTM policy

Bug Fixes
`````````
* [OPENSTACK-2262] Fix IPv6 redirect host parsing
* [OPENSTACK-2350]fix: depercated --customized insertXforwardedFor
* [OPENSTACK-2350] fix: TOA update need to delete profile and iRule
* [OPENSTACK-2342] fix: selfip recreating fails to catch HTTP 409
* [OPENSTACK-2341] fix: get all nodes in a partition

Limitations
```````````

v9.8.47 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* [OPENSTACK-2224] new way for health monitor timeout
* [OPENSTACK-2223] add UDP health monitor type

Bug Fixes
`````````
* [OPENSTACK-2214] If member already exists, it causes HTTP 409 ERROR
* [OPENSTACK-2286] Fix deb requirements
* [OPENSTACK-2277] Add a periodic config save task to save the configuration
* [OPENSTACK-2282] Fix resources creation conflict issue
* [OPENSTACK-2294] Multiple agents updating snatpool member causes bigip incosistency problem
* [OPENSTACK-2295] Ensure route domain id consistency

Limitations
```````````

v9.8.46 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Feature change member update process

Bug Fixes
`````````
* Fix the KeyError issue of heartbeat periodic task.
* Fix typo fix from reponse to response
* Fix rds cache pollute problem
* Fix project named route domain
* Fix check project_id at global_routed_mode is True
* Fix bigip status check
* Fix cleanup all snat, vlan and self ip before removing partition
* Fix only check nodes in current partition
* Fix Catch all exception for route domain creation
* Fix periodic_interval
* Upgrade eventlet to version 0.31.0 for Dependabot vulnerable
* Fix the issue of deleting nodes and snat in bigip ha mode
* add checking status support and don't send the members with status of none or checking

Limitations
```````````

v9.8.45 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Change the algorithm from least-connection-node to least-connection-member for source_ip algorithm in neutorn
* Use HEAD or GET for monitor
* Remove persist profile from vs, if its default pool remove persistence
* When update listener with customized paramater then bind the new http profile to the listener

Bug Fixes
`````````
* Error loadbalancer cannot delete, cause of no partition
* Fix the issue of route domain issue: id already exists.
* Fix some logs
* Fix log type
* Will not del the vs customized property. It will use when configuring the other bigips in cluster mode
* The extra items such as customized, tls in payload will cause error for updating operation

Limitations
```````````

v9.8.44 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Add lbaas-listener-update --customized support.
* Add avaliability_zone configuration for agenting state reporting
* Ensure to overwrite persistence profile
* Tolerate persistence timeout in string type

Bug Fixes
`````````
* Fix customized bug of vs == None
* Handle both None and '' situations for listener['customized']
* Fix 'error opening BIG-IP - active:BIG-IP ready for provisioning'

Limitations
```````````

v9.8.43 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Support to modify client ca certificate
* Support client authentication
* Add '--customized' support for listener creation.
* Support session persistence timeout parameter in API
* Customerised timeout value in persistence iRule and tolerate negative or None value of persistence_timeout
* Change icontrol heartbeat interval as same as _report_state.
* Support to modify lb operating_status accordingly

Bug Fixes
`````````
* Fix listener exception log
* Fix member batch deletion breakdown
* Remove obsolete bwc code
* Throw exception if no active bigips
* FIX backwards compatibility problem of SNAT pool member name.

Limitations
```````````

v9.8.42 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````

Bug Fixes
`````````
* FIX backwards compatibility problem of SNAT pool member name.

Limitations
```````````

v9.8.41 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Remove the previous bwc function

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
