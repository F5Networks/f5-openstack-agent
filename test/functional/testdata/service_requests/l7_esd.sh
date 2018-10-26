#!/bin/sh

neutron lbaas-loadbalancer-create --name lb1 testlab-server-v4-subnet
sleep 5s
neutron lbaas-listener-create --name listener1 --protocol HTTP --protocol-port 80 --loadbalancer lb1
sleep 5s
neutron lbaas-pool-create --name pool1 --listener listener1 --lb-algorithm ROUND_ROBIN --protocol HTTP --session-persistence type=HTTP_COOKIE
sleep 5s
neutron lbaas-l7policy-create --name esd_demo_1 --listener listener1 --action REJECT
sleep 5s
neutron lbaas-l7policy-delete esd_demo_1
sleep 5s
neutron lbaas-l7policy-create --name esd_demo_2 --listener listener1 --action REJECT
sleep 5s
neutron lbaas-l7policy-delete esd_demo_2
sleep 5s
neutron lbaas-pool-delete pool1
sleep 5s
neutron lbaas-listener-delete listener1
sleep 5s
neutron lbaas-loadbalancer-delete lb1
