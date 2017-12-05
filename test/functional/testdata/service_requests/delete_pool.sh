#!/bin/sh

neutron lbaas-loadbalancer-create --name lb1 lb-subnet
sleep 5s
neutron lbaas-listener-create --name listener1 --loadbalancer lb1 --protocol HTTP --protocol-port 80 
sleep 5s
neutron lbaas-pool-create --name pool1 --listener listener1 --protocol HTTP --lb-algorithm ROUND_ROBIN
sleep 5s
neutron lbaas-member-create --address 192.168.200.30 --protocol-port 80 --subnet member-subnet pool1
sleep 5s
neutron lbaas-member-create --address 192.168.200.40 --protocol-port 80 --subnet member-subnet pool1
sleep 25s
neutron lbaas-pool-delete pool1 
sleep 5s
neutron lbaas-listener-delete listener1 
sleep 5s
neutron lbaas-loadbalancer-delete lb1 
