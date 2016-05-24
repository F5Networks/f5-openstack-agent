Configure the F5® OpenStack Agent
---------------------------------

Overview
````````

To use the F5® OpenStack agent, edit the config file -- :file:`/etc/neutron/services/f5/f5-openstack-agent.ini` -- as appropriate for your environment.

Below, we've provided an overview of the configuration options available for the current release, |release|. All of the agent's functions are described in detail in the :ref:`agent configuration file <agent-configuration-file>`. You can also see the :ref:`Release Notes <release-notes>` for more information about these features.


Configurable Features
`````````````````````

Device Settings
^^^^^^^^^^^^^^^

    .. code-block:: text

        # HA model
        #
        # ...
        #
        f5_ha_type = standalone
        #
        #
        # Sync mode
        #
        # ...
        #
        f5_sync_mode = replication
        #

L2/L3 Segmentation Mode Settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    .. code-block:: text

        # Device VLAN to interface and tag mapping
        #
        # ...
        #
        f5_external_physical_mappings = default:1.1:True
        #

    .. code-block:: text

        # Device Tunneling (VTEP) selfips
        #
        # ...
        #
        f5_vtep_folder = 'Common'
        f5_vtep_selfip_name = '<name of a vtep selfip>'
        #
        #

    .. code-block:: text

        # Tunnel types
        #
        # ...
        #
        advertised_tunnel_types = 'gre' \\ 'vxlan' \\ 'gre,vxlan'
        #
        #

Global Routed Mode Settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^

    .. code-block:: text

        # Global Routed Mode - No L2 or L3 Segmentation on BIG-IP®
        ...
        #
        f5_global_routed_mode = True \\ False
        #

Device Driver - iControl® Driver Setting
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    .. code-block:: text

        #
        icontrol_hostname = 10.190.6.105 \\ replace with the IP address of your BIG-IP®
        #
        # ...
        #
        icontrol_username = admin
        #
        icontrol_password = admin
        #


