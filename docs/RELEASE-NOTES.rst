.. index:: Release Notes

.. _Release Notes:

Release Notes for F5 Openstack Agent
====================================

v9.8.0 (Mitaka, Newton, Ocata, Pike)
------------------------------------
NOTE: This version of F5 Openstack Agent will support Mitaka, Newton, Ocata and Pike Openstack releases.

Added Functionality
```````````````````
* Enhanced Advanced Load Balancer(ALB).

  - Add 2 profile types support in Enhanced Service Definition(ESD):

    - HTTP profile.
    - OneConnect profile.

  - Expose ESD API to Native Neutron L7 Policy CLI(Neutron Node)

Bug Fixes
`````````

- Can't create self ip in both units using the same route domain ids.
- Agent deletes incorrect route domain.

Limitations
```````````
