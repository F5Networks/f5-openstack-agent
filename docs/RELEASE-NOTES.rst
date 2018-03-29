.. index:: Release Notes

.. _Release Notes:

Release Notes
=============

v10.2.0
-------

Added Functionality
```````````````````
* Enhanced F5 Agent resiliency.
  - F5 Agents manage BIG-IPs dynamically, resulting in improved tolerance for BIG-IP device failures.
  - F5 Agents will continue to run during BIG-IP device downtime and discover when BIG-IP devices come back online.

* Improved Enhanced Services Definition (ESD).
  - Refer to the `ESD documentation`_ for details.

Bug Fixes
`````````
* See the `changelog <https://github.com/F5Networks/f5-openstack-agent/compare/v10.1.0...v10.2.0>`_ for the full list of changes in this release.

Limitations
```````````
* The |agent| supports enabling static ARP entries on BIG-IP devices running version 12.x or later.
