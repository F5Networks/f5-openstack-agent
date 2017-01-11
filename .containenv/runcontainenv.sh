#! /bin/bash

docker run -it -e USER=${USER} \
               -e USER_ID=`id -u -r` \
               -v /var/run/docker.sock:/var/run/docker.sock \
               -v ${HOME}:/home/${USER} \
               f5-openstack-agent_containenv