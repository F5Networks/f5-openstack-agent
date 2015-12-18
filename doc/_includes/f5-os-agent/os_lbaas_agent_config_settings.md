<table width="797">
<tbody>
<tr>
<td colspan="2" width="797">F5 OpenStack LBaaS Agent Configuration Options</td>
</tr>
<tr>
<td width="341">[DEFAULT]</td>
<td width="456">&nbsp;</td>
</tr>
<tr>
<td width="341">debug = True</td>
<td width="456">Show debugging output in log (sets DEBUG log level output).</td>
</tr>
<tr>
<td width="341">periodic_interval = 10</td>
<td width="456">The LBaaS agent will resync its state with Neutron to recover from any transient notification or rpc errors. The periodic interval is number of seconds between attempts.</td>
</tr>
<tr>
<td width="341">service_resync_interval = 500</td>
<td width="456">How often the agent throws away its service cache and resyncs assigned services with the neutron LBaaS plugin.</td>
</tr>
<tr>
<td width="341">environment_prefix = uuid</td>
<td width="456">The environmental prefix that the agent applies to BIG-IP objects it creates. The default setting is 'uuid'.</td>
</tr>
<tr>
<td colspan="2" width="797">WARNING: You should set the environmental prefix before creating any BIG-IP objects. If you change it after you've created objects, those objects will no longer be associated with the agent and will have to be managed manually.</td>
</tr>
<tr>
<td width="341">static_agent_configuration_data = name1:value1, name1:value2, name3:value3</td>
<td width="456">Static configuration data to send back to the plugin. A single entry, or a comma-separated list of name:value entries, which will be sent in the agent's configuration dictionary to Neutron. This can be used on the plugin side of Neutron to provide agent identification for custom pool-to-agent scheduling.</td>
</tr>
<tr>
<td width="341">Device Setting</td>
<td width="456">Device type for LBaaS</td>
</tr>
<tr>
<td width="341">f5_device_type = external</td>
<td width="456">external - external (hardware or VE)</td>
</tr>
<tr>
<td width="341">f5_device_type = guest_admin</td>
<td width="456">guest_admin - VE created under the admin tenant</td>
</tr>
<tr>
<td>f5_device_type = guest_tenant</td>
<td width="456">guest_tenant - VE created under the pool tenant</td>
</tr>
<tr>
<td width="341">HA model</td>
<td width="456">Set High Availability (HA) model</td>
</tr>
<tr>
<td width="341">f5_ha_type = standalone</td>
<td width="456">Single device, no HA</td>
</tr>
<tr>
<td width="341">f5_ha_type = pair</td>
<td width="456">Active/standby two-device HA</td>
</tr>
<tr>
<td width="341">f5_ha_type = scalen</td>
<td width="456">Active device cluster</td>
</tr>
<tr>
<td colspan="2" width="797">Note: If the device is external, the devices must be onboarded for the appropriate HA mode or else the driver will not provision devices.</td>
</tr>
<tr>
<td width="341">Sync mode</td>
<td width="456">Set policy sharing across devices</td>
</tr>
<tr>
<td width="341">f5_sync_mode = autosync</td>
<td width="456">Syncable policies configured on one device are synced to the group.</td>
</tr>
<tr>
<td width="341">f5_sync_mode = replication</td>
<td width="456">Each device is configured separately.</td>
</tr>
<tr>
<td width="341">L2 Segmentation Mode Settings</td>
<td width="456">Configure L2 segmentation for pools or VIPs created on VLAN networks</td>
</tr>
<tr>
<td rowspan="4" width="341">Device VLAN to interface and tag mapping</td>
<td width="456">A comma-separated list of strings that specifiy to which interface the agent should map a VLAN and state if VLAN tagging should be enforced by the external device. The string should use the following format: "physical_network:interface_name:tagged".</td>
</tr>
<tr>
<td width="456">'"physical_network" corresponds to "provider:physical_network" attributes</td>
</tr>
<tr>
<td width="456">"interface_name" is the name of an interface or LAG trunk</td>
</tr>
<tr>
<td width="456">"tagged" is a boolean (True or False)</td>
</tr>
<tr>
<td width="341">standalone:</td>
<td width="456">&nbsp;</td>
</tr>
<tr>
<td width="341">f5_external_physical_mappings = default:1.1:True</td>
<td width="456">Maps the 'default' physical network to interface '1.1' with tagging enforced.</td>
</tr>
<tr>
<td width="341">pair or scalen:</td>
<td width="456">&nbsp;</td>
</tr>
<tr>
<td width="341">f5_external_physical_mappings = default:1.3:True</td>
<td width="456">Maps the 'default' physical network to interface '1.3' with tagging enforced.</td>
</tr>
<tr>
<td colspan="2" width="797">Note: If a network does not have a provider:physical_network attribute, or the provider:physical_network attribute does not match in the configured list, the 'default' physical_network setting is applied. At a minimum, you must have a 'default' physical_network setting. The '1.1' and '1.2' interfaces are used for HA purposes.</td>
</tr>
<tr>
<td width="341">Device Tunneling (VTEP) self-ips</td>
<td width="456">A single entry or a comma-separated list of cidr (h/m) format self-ip addresses - one per BIG-IP device - to use for VTEP addresses.</td>
</tr>
<tr>
<td width="341">f5_vtep_folder = 'Common'</td>
<td width="456">Sets the VTEP to use the default partition ("Common") on the BIG-IP.</td>
</tr>
<tr>
<td width="341">f5_vtep_selfip_name = 'vtep'</td>
<td width="456">Sets the VTEP self-ip name to "vtep".</td>
</tr>
<tr>
<td width="341">Tunnel types</td>
<td width="456">A comma-separated list of tunnel types to report as available from this agent and to send to compute nodes via tunnel_sync rpc messages. This should match the ml2 network types on your compute nodes.</td>
</tr>
<tr>
<td width="341">advertised_tunnel_types = gre</td>
<td width="456">use only gre tunnels</td>
</tr>
<tr>
<td width="341">advertised_tunnel_types = vxlan</td>
<td width="456">use only vxlan tunnels</td>
</tr>
<tr>
<td width="341">advertised_tunnel_types = gre,vxlan</td>
<td width="456">use gre and vxlan tunnel networks</td>
</tr>
<tr>
<td width="341">advertised_tunnel_types = vlan</td>
<td width="456">use only vlans</td>
</tr>
<tr>
<td colspan="2" width="797">Note: If no gre or vxlan tunneling is required, these settings should be commented out or set to None.</td>
</tr>
<tr>
<td width="341">Static ARP population for members on tunnel networks</td>
<td width="456">Creating a static ARP entry allows the agent to avoid having to learn Pool Members' MAC addresses via flooding. Use a boolean "True" or "False" entry to specify whether an entry should be created if a Pool Member IP address is associated with a gre or vxlan tunnel network and a tunnel fdb record is added.</td>
</tr>
<tr>
<td width="341">f5_populate_static_arp = True</td>
<td width="456">Sets the agent to create a static arp entry.</td>
</tr>
<tr>
<td width="341">Device Tunneling (VTEP) selfips</td>
<td width="456">A boolean "True" or "False" entry which determines if the BIG-IP will use L2 Population service to update its fdb tunnel entries.</td>
</tr>
<tr>
<td width="341">l2_population = True</td>
<td width="456">Tells the agent to configure the BIG-IP to use L2 Population service to update fbd tunnel entries.</td>
</tr>
<tr>
<td colspan="2">Note: This needs to be set up in parallel with the tunnel agents. If the BIG-IP and tunnel agent settings don't match, the tunnel setup will not work properly.</td>
</tr>
</tbody>
</table>