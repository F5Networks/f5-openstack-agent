Install the F5 OpenStack Agent
------------------------------

Quick Start
```````````

.. rubric:: Install the ``f5-openstack-agent`` package for v |release|:

.. parsed-literal::

    $ sudo pip install |f5_agent_pip_url|

.. tip::

    You can install packages from HEAD on a specific branches by adding ``@<branch_name>`` to the end of the install command instead of the release tag.

    .. rubric:: Example:
    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@stable/newton


Debian Package
``````````````

The ``f5-openstack-agent`` package can be installed using ``dpkg`` tools.

1. Download and install the dependencies:

.. parsed-literal::

    $ curl -L -O |f5_sdk_deb_url|
    $ curl -L -O |f5_icontrol_deb_url|
    $ sudo dpkg –i |f5_icontrol_deb_package|
    $ sudo dpkg –i |f5_sdk_deb_package|

2. Download and install the f5-openstack-agent:

.. parsed-literal::

    $ curl -L -O |f5_agent_deb_url|
    $ sudo dpkg –i |f5_agent_deb_package|


RPM Package
```````````

The ``f5-openstack-agent`` package can be installed using ``rpm`` tools.

1. Download and install the dependencies:

.. parsed-literal::

    $ curl -L -O |f5_sdk_rpm_url|
    $ curl -L -O |f5_icontrol_rpm_url|
    $ sudo rpm -ivh |f5_icontrol_rpm_package| |f5_sdk_rpm_package|


2. Download and install the f5-openstack-agent:

.. parsed-literal::

    $ curl -L -O |f5_agent_rpm_url|
    $ sudo rpm –ivh |f5_agent_rpm_package|



Next Steps
``````````

Next, :ref:`install the f5-openstack-lbaasv2-driver <lbaasv2driver:Install the F5 LBaaSv2 Driver>`.


Need to Upgrade?
````````````````

Please see the :ref:`upgrade instructions <lbaasv2driver:Upgrading the F5 LBaaSv2 Components>`.
