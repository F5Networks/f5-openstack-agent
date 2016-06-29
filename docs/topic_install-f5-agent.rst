Install the F5 OpenStack Agent
------------------------------

.. note::

    - You must have both ``pip`` and ``git`` installed on your machine in order to use these commands.
    - It may be necessary to use ``sudo``, depending on your environment.

.. topic:: To install the ``f5-openstack-agent`` package from the |openstack| branch:

    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@mitaka

.. topic:: To install the ``f5-openstack-agent`` release package for v |version|:

    You can install specific releases by adding ``@<release_tag>`` to the end of the install command.

    For example:

    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@v9.0.1


Need to Upgrade?
````````````````

Please see the :ref:`upgrade instructions <lbaasv2driver:Upgrading the F5 LBaaSv2 Components>`.
