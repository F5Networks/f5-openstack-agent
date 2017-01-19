#! /bin/bash
useradd $USER -u $USER_ID -G sudo,docker,staff &&\
echo $USER' ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers &&\
exec su - $USER
