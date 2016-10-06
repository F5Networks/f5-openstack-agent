#!/usr/bin/env bash
set -ex

if [ "$1" == "" ]; then
    echo "ERROR: no repo value provided!"
    exit 1
else
    repo="$1"
fi

if [ "$2" == "" ]; then
    echo "ERROR: no branch value provided!"
    exit 1
else
    branch="$2"
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

#Install the agent
sudo rm -rf f5-openstack-agent
git clone -b $branch $repo
cd f5-openstack-agent
pip install --upgrade .

# Install openstack deps (if necessary)
pip install git+https://github.com/openstack/neutron#stable/$branch
pip install git+https://github.com/openstack/oslo.log.git@stable/$branch
pip install git+https://github.com/openstack/neutron-lbaas.git@stable/$branch

# Install driver
pip install git+https://github.com/F5Networks/f5-openstack-lbaasv2-driver.git@$branch

# Install local test utils
pip install git+https://github.com/F5Networks/f5-openstack-test.git
pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-meta.git
pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-symbols.git
pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-autolog.git

# Install general test utils
pip install f5-sdk==1.5.0
pip install mock==2.0.0
pip install pytest==3.0.3
pip install pytest-cov==2.3.1
pip install responses==0.5.1
pip install coverage==4.2
pip install python-coveralls==2.8.0
