.. toctree::
    :hidden:

Release Notes |release|
=======================

This release provides an implementation of the F5® agent to support the use of F5 Networks® BIG-IP® systems with OpenStack Neutron LBaaSv2.

Release Highlights
------------------

This release introduces support for the following:

* Listener ``TERMINATED_HTTPS`` protocol (SSL offloading)
* BIG-IP® device clusters (``active-standby`` and ``scalen`` configurations).

Caveats
-------

The following features are unsupported in v8.0.3:

* `BIG-IP® vCMP® <https://f5.com/resources/white-papers/virtual-clustered-multiprocessing-vcmp>`_
* Agent High Availability (HA)
* Auto-sync mode for clustered devices
* Differentiated environments
* Loadbalancer statistics

Open Issues
-----------

See the `project issues page <https://github.com/F5Networks/f5-openstack-agent/issues>`_ for a full list of open issues in this release.

Documentation can be found on `Read the Docs <http://f5-openstack-lbaasv2-driver.readthedocs.io/en/latest/release_notes.html>`_.




