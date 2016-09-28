Install the F5 OpenStack Agent
------------------------------

Quick Start
```````````

.. rubric:: Install the ``f5-openstack-agent`` package for v |release|:

.. code-block:: text

    $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@v8.0.8

.. tip::

    You can install packages from HEAD on a specific branches by adding ``@<branch_name>`` to the end of the install command instead of the release tag.

    .. rubric:: Example:
    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@liberty


Debian Package
``````````````

The ``f5-openstack-agent`` package can be installed using ``dpkg`` tools.

1. Download and install the dependencies:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-common-python/releases/download/v1.2.0/python-f5–sdk_1.2.0–1_1404_all.deb
    $ curl -L -O https://github.com/F5Networks/f5-icontrol-rest-python/releases/download/v1.0.9/python-f5-icontrol-rest_1.0.9-1_1404_all.deb
    $ sudo dpkg –i python-f5-icontrol-rest_1.0.9-1_1404_all.deb
    $ sudo dpkg –i python-f5–sdk_1.2.0–1_1404_all.deb

2. Download and install the f5-openstack-agent:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-openstack-agent/releases/download/v8.0.8/python-f5-openstack-agent_8.0.8-1_1404_all.deb
    $ sudo dpkg –i python-f5-openstack-agent_8.0.8-1_1404_all.deb


RPM Package
```````````

The ``f5-openstack-agent`` package can be installed using ``rpm`` tools.

1. Download and install the dependencies:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-common-python/releases/download/v1.2.0/f5-sdk-1.2.0-1.el7.noarch.rpm
    $ curl -L -O https://github.com/F5Networks/f5-icontrol-rest-python/releases/download/v1.0.9/f5-icontrol-rest-1.0.9-1.el7.noarch.rpm
    $ sudo rpm –ivh f5-icontrol-rest-1.0.9-1.el7.noarch.rpm f5-sdk-1.2.0-1.el7.noarch.rpm


2. Download and install the f5-openstack-agent:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-openstack-agent/releases/download/v8.0.8/f5-openstack-agent-8.0.8-1.el7.noarch.rpm
    $ sudo rpm –ivh f5-openstack-agent-8.0.8-1.el7.noarch.rpm



Next Steps
``````````

Next, :ref:`install the f5-openstack-lbaasv2-driver <lbaasv2driver:Install the F5 LBaaSv2 Driver>`.


Need to Upgrade?
````````````````

Please see the :ref:`upgrade instructions <lbaasv2driver:Upgrading the F5 LBaaSv2 Components>`.
