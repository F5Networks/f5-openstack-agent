Install the F5® OpenStack Agent
-------------------------------

.. note::

    - You must have both ``pip`` and ``git`` installed on your machine in order to use these commands.
    - It may be necessary to use ``sudo``, depending on your environment.

.. topic:: To install the ``f5-openstack-agent`` package:

    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent

.. important::

    The command above will install the package from the default branch in GitHub (liberty). You can install specific releases by adding ``@<release_tag>`` to the end of the install command.

    For example:

    .. code-block:: text

        $ sudo pip install git+https://github.com/F5Networks/f5-openstack-agent@v8.0.2

