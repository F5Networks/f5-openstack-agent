NextGen Inventory CLI

NextGen design doc: https://gitswarm.f5net.com/qzhao/misc/-/blob/master/docs/lbaasv2-ng.md

### 1. bigip-onboard create
usage: add BIG-IP to credential

required params:
- icontrol_hostname: BIG-IP icontrol API hostname
- icontrol_username: BIG-IP icontrol API username
- icontrol_password: BIG-IP icontrol API password

positional params:
- id: credential id of BIG-IP device group, id should be specified when add new BIG-IP to existing group.
- availability_zone: availability zone of BIG-IP group, default null.
- icontrol_port: BIP-IP icontrol API port, default 443.

command example:
1. add a new BIG-IP to a new device group

`bigip-onboard create 10.145.76.72 admin admin@f5.com --availability_zone nova 
`
2. add a new BIG-IP to a existing group

`bigip-onboard create 10.145.75.174 admin admin@f5.com --id 7f293e491d2445048c8ce894bd027ccb 
`
### 2. bigip-onboard delete
usage: removing BIG-IP from existing group

required params:
- id: credential id of BIG-IP device group which 
- icontrol_hostname: hostname of BIG-IP to be removed

command example:

`bigip-onboard delete 7f293e491d2445048c8ce894bd027ccb 10.145.75.174 
`
### 3. bigip-onboard update
usage: update admin properties of BIG-IP group

required params:
- id: credential id of BIG-IP group

positional params:
- admin-state-down: when this param exist in the command, admin_state_up property will be set _false_. 
(The updating logic is same as `neutron agent-update`)
- availability_zone: availability zone of BIG-IP group

command example:
1. updating admin_state_up to false.

`bigip-onboard update 7f293e491d2445048c8ce894bd027ccb --admin-state-down`

2. updating availability_zone

`bigip-onboard update 7f293e491d2445048c8ce894bd027ccb --availability_zone test`

### 4. bigip-onboard refresh
usage: refresh device properties of BIG-IP

required params:
- id: credential id of BIG-IP group
- icontrol_hostname: hostname of BIG-IP to be refreshed

command example:

`bigip-onboard refresh 7f293e491d2445048c8ce894bd027ccb 10.145.75.174`

