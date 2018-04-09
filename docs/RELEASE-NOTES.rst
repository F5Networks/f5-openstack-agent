.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.6.0 (Mitaka, Newton, Ocata, Pike)
------------------------------------
NOTE: This version of F5 Openstack Agent will support Mitaka, Newton, Ocata and Pike Openstack releases.

Added Functionality
```````````````````
* Enhanced Agent logging:
  - Set default logging to False.
  - Enable f5-sdk debug logging when Agent logging is True.

Bug Fixes
`````````
* :issues:`1242` - Agent not properly handling invalid network exceptions.
* :issues:`1244` - agent logging getting propagated over to /var/log/messages or /var/log/syslog.
* :issues:`1291` - Tagmode incorrectly set when creating VLANs.

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
