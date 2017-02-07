#!/bin/sh

neutron lbaas-loadbalancer-create --name lb1 testlab-mgmt-v4-subnet
sleep 5s
neutron lbaas-listener-create --name listener1 --protocol HTTP --protocol-port 80 --loadbalancer lb1
sleep 5s
neutron lbaas-listener-create --name listener2 --protocol HTTPS --protocol-port 443 --loadbalancer lb1
sleep 5s
neutron lbaas-pool-create --name pool1 --listener listener1 --lb-algorithm ROUND_ROBIN --protocol HTTP
sleep 5s
neutron lbaas-healthmonitor-create --name hm1 --type HTTP --delay 10 --max-retries 5 --timeout 5 --pool pool1
sleep 5s
neutron lbaas-pool-create --name pool2 --listener listener2 --lb-algorithm ROUND_ROBIN --protocol HTTPS
sleep 5s
neutron lbaas-healthmonitor-create --name hm2 --type HTTP --delay 10 --max-retries 5 --timeout 5 --pool pool2
sleep 5s
neutron lbaas-member-create  --address 10.2.1.2 --protocol-port 8080 --subnet testlab-mgmt-v4-subnet  pool1
sleep 5s
neutron lbaas-member-create  --address 10.2.1.2 --protocol-port 8080 --subnet testlab-mgmt-v4-subnet  pool2
sleep 5s
neutron lbaas-healthmonitor-delete hm1
sleep 5s
neutron lbaas-healthmonitor-delete hm2
sleep 5s
neutron lbaas-pool-delete pool1
sleep 5s
neutron lbaas-pool-delete pool2
sleep 5s
neutron lbaas-listener-delete listener1
sleep 5s
neutron lbaas-listener-delete listener2
sleep 5s
neutron lbaas-loadbalancer-delete lb1
