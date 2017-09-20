.. _device-driver-settings:

.. index::
   single: f5-openstack-agent; device driver settings

.. index::
   single: f5-openstack-agent; iControl driver settings

.. index::
   single: f5-openstack-agent; BIG-IP setup

Device Driver Settings/iControl Driver Settings
===============================================

The Device Driver Settings in the :ref:`F5 Agent Configuration File` provide the means of communication between the |agent-long| and BIG-IP device(s). **Do not change this setting**.

The iControl Driver Settings identify the BIG-IP device(s) that you want the |agent-short| to manage and record the login information the agent will use to communicate with the BIG-IP(s).

If you want to use the |agent-long| to manage BIG-IP devices from within your OpenStack cloud, you **must** provide the correct information in this section of the agent config file.
The |agent-short| can manage a :term:`standalone` device or a :term:`device service cluster`.

.. seealso::

   `Manage BIG-IP Clusters with F5 LBaaSv2 </cloud/openstack/latest/lbaas/manage-bigip-clusters>`_


Configuration
-------------

.. include:: /_static/reuse/edit-agent-config-file.rst

#. Enter the iControl endpoint(s), username, and password for your BIG-IP(s).

    * :code:`icontrol_hostname`: The IP address(es) of the BIG-IP(s) the agent will manage. If you're using multiple devices, provide a comma-separated list containing the management IP address of each device.
    * :code:`icontrol_vcmp_hostname`: The IP address(es) of the BIG-IP device(s) used for `vCMP`_
    * :code:`icontrol_username`: The username of the adminstrative user; *must have access to all BIG-IP devices*.
    * :code:`icontrol_password`: The password of the adminstrative user; *must have access to all BIG-IP devices*.

   .. code-block:: text

      ###############################################################################
      #  Device Driver - iControl Driver Setting
      ###############################################################################
      #
      icontrol_hostname = 10.190.7.232 \\ replace with the IP address(es) of your BIG-IP(s)
      #
      # icontrol_vcmp_hostname = 192.168.1.245
      #
      icontrol_username = admin
      #
      icontrol_password = admin
      #

#. Set up the |agent-long| to use :ref:`L2-adjacent mode <l2-adjacent-setup>` or :ref:`Global Routed mode <global-routed-setup>`.

.. _vCMP: /cloud/openstack/v1/lbaas/lbaas-manage-vcmp.html
