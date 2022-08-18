NextGen Inventory CLI

### 1. bigip-onboard create
usage: Create BIG-IP to device group

required params:
- icontrol_hostname: BIG-IP icontrol API hostname
- icontrol_username: BIG-IP icontrol API username
- icontrol_password: BIG-IP icontrol API password

positional params:
- id: credential id of BIG-IP device group, id should be specified when add new BIG-IP to existing group.
- availability_zone: availability zone of BIG-IP group, default null.
- icontrol_port: BIP-IP icontrol API port, default 443.

command example:
1. Create a new bigip to a new device group

    `bigip-onboard create 10.145.76.72 admin admin@f5.com --availability_zone nova 
`
2. Create a new bigip to an existing device group

    `bigip-onboard create 10.145.75.174 admin admin@f5.com --id 7f293e491d2445048c8ce894bd027ccb`

### 2. bigip-onboard delete
usage: Remove a existing bigip from an existing device group

required params:
- id: credential id of BIG-IP device group
- icontrol_hostname: hostname of BIG-IP to be removed

command example:

`bigip-onboard delete 7f293e491d2445048c8ce894bd027ccb 10.145.75.174`

### 3. bigip-onboard update
usage: Modify the admin properties of an existing bigip in an existing device group

required params:
- id: credential id of BIG-IP group

positional params:
- admin-state-down: when this param exist in the command, `admin_state_up` property will be set `false`. 
(The updating logic is same as `neutron agent-update`)
- availability_zone: availability zone of BIG-IP group

command example:
1. update admin_state_up to `false`.

    `bigip-onboard update 7f293e491d2445048c8ce894bd027ccb --admin-state-down`

2. update availability_zone to `test`

    `bigip-onboard update 7f293e491d2445048c8ce894bd027ccb --availability_zone test`

### 4. bigip-onboard refresh
usage: Refresh the device properties of an existing bigip in an existing device group

required params:
- id: credential id of BIG-IP group
- icontrol_hostname: hostname of BIG-IP to be refreshed

command example:

`bigip-onboard refresh 7f293e491d2445048c8ce894bd027ccb 10.145.75.174`

