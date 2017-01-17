Install the F5 OpenStack Agent
------------------------------

Quick Start
```````````

.. rubric:: Install the ``f5-openstack-agent`` package for v |release|:

.. code-block:: text

    $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@v9.2.0

.. tip::

    You can install packages from HEAD on a specific branches by adding ``@<branch_name>`` to the end of the install command instead of the release tag.

    .. rubric:: Example:
    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@mitaka


Debian Package
``````````````

The ``f5-openstack-agent`` package can be installed using ``dpkg`` tools.

1. Download and install the dependencies:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-common-python/releases/download/v2.1.0/python-f5-sdk_2.1.0-1_1404_all.deb
    $ curl -L -O https://github.com/F5Networks/f5-icontrol-rest-python/releases/download/v1.1.0/python-f5-icontrol-rest_1.1.0-1_1404_all.deb
    $ sudo dpkg –i python-f5-icontrol-rest_1.1.0-1_1404_all.deb
    $ sudo dpkg –i python-f5-sdk_2.1.0-1_1404_all.deb

2. Download and install the f5-openstack-agent:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-openstack-agent/releases/download/v9.2.0/python-f5-openstack-agent_9.2.0-1_1404_all.deb
    $ sudo dpkg –i python-f5-openstack-agent_9.2.0-1_1404_all.deb


RPM Package
```````````

The ``f5-openstack-agent`` package can be installed using ``rpm`` tools.

1. Download and install the dependencies:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-common-python/releases/download/v2.1.0/f5-sdk-2.1.0-1.el7.noarch.rpm
    $ curl -L -O https://github.com/F5Networks/f5-icontrol-rest-python/releases/download/v1.1.0/f5-icontrol-rest-1.1.0-1.el7.noarch.rpm
    $ sudo rpm –ivh f5-icontrol-rest-1.1.0-1.el7.noarch.rpm f5-sdk-2.1.0-1.el7.noarch.rpm


2. Download and install the f5-openstack-agent:

.. code-block:: bash

    $ curl -L -O https://github.com/F5Networks/f5-openstack-agent/releases/download/v9.2.0/f5-openstack-agent-9.2.0-1.el7.noarch.rpm
    $ sudo rpm –ivh f5-openstack-agent-9.2.0-1.el7.noarch.rpm


Next Steps
``````````

Next, :ref:`install the f5-openstack-lbaasv2-driver <lbaasv2driver:Install the F5 LBaaSv2 Driver>`.


Need to Upgrade?
````````````````

Please see the :ref:`upgrade instructions <lbaasv2driver:Upgrading the F5 LBaaSv2 Components>`.
