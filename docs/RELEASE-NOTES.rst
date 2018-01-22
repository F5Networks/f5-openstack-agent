Release Notes for F5 LBaaS Agent
=================================

v10.2.0 (Newton)
----------------

Added Functionality
```````````````````
* Enhanced agent resiliency. 
  - Agents manage BIG-IPs dynamically, resulting in improved tolereance for BIG-IP device failures.
  - Agents will continue to run during BIG-IP device downtime and discover when BIG-IP devices come back online.

* Improved Enhanced Services Definition (ESD).
  - Refer to the ESD documentation for details.

Bug Fixes
`````````
* See the [changelog](https://github.com/F5Networks/f5-openstack-agent/compare/v10.1.0...v10.2.0) for the full list of changes in this release.

Limitations
```````````
* Enabling  static ARP entries is suported for BIG-IP devices running version 12.x or later.
