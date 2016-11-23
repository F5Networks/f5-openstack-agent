#!/usr/bin/env bash
set -ex

if [ "$1" == "" ]; then
    echo "ERROR: no session value provided!"
    exit 1
else
    session="$1"
fi

# - create the local results directory
results_dir="~/test_results"
if [[ ! -e "$results_dir" ]]; then
    mkdir -p "$results_dir"
fi

# enter the systext virtualenv
source systest/bin/activate

# - run the system tests
cd ~/f5-openstack-agent/test/functional/neutronless/disconnected_service

py.test \
    -vx \
    --symbols ~/testenv_symbols/testenv_symbols.json \
    --exclude incomplete no_regression \
    --autolog-outputdir $results_dir \
    --autolog-session $session \
    -- .
