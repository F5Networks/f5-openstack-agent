#!/usr/bin/env bash
set -ex

if [ "$1" == "" ]; then
    echo "ERROR: no repo value provided!"
    exit 1
else
    repo="$1"
fi

# - work around the "unknown host" prompt
fl=~/.ssh/config
opt="StrictHostKeyChecking no"
if [[ ! -e $fl ]] || [[ $(grep "^$opt" $fl | wc -l) == 0 ]]; then
    echo "$opt" >> $fl
fi

sudo apt-get update && sudo apt-get install -y libssl-dev
sudo apt-get install -y libffi-dev
pip install virtualenv
virtualenv systest
source systest/bin/activate

# - install system 
branch="feature.bb_integration_331"
sudo rm -rf f5-openstack-agent
git clone -b $branch $repo
cd f5-openstack-agent
pip install -r ./requirements.buildbot.txt
cd ~
rm -rf f5-common-python
git clone -b development https://github.com/F5Networks/f5-common-python.git
cd f5-common-python
pip install --upgrade .
