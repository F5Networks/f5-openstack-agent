.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.8.30 (Pike, Queens)
--------------------------------------------
NOTE: This version of F5 Openstack Agent supports Pike and Queens Openstack releases.

Added Functionality
```````````````````
* Support port number 0
* Add a placeholder for bulk

Bug Fixes
`````````

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
