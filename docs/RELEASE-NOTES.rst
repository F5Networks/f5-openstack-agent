.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

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
