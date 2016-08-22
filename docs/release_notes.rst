.. toctree::
    :hidden:

Release Notes v |release|
=========================

This release provides an implementation of the F5® agent to support the use of F5 Networks® BIG-IP® systems with OpenStack Neutron LBaaSv2.

Release Highlights
------------------

This release introduces the following:

- Installation via rpm
- Installation via dpkg
- Uses either Keystone Auth1 or Keystone Client python library
- Bug fixes

See the `changelog <https://github.com/F5Networks/f5-openstack-agent/compare/v9.0.2...v9.0.3>`_ for the full list of changes in this release.

Caveats
-------

The following features are unsupported in v |release|:

* `BIG-IP® vCMP® <https://f5.com/resources/white-papers/virtual-clustered-multiprocessing-vcmp>`_
* Agent High Availability (HA)
* Differentiated environments
* Unattached pools
* L7 routing
* Loadbalancer statistics

Open Issues
-----------

See the `project issues page <https://github.com/F5Networks/f5-openstack-agent/issues>`_ for a full list of open issues in this release.

Documentation can be found on `Read the Docs <http://f5-openstack-lbaasv2-driver.readthedocs.io/en/latest/release_notes.html>`_.




