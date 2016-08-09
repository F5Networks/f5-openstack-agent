#!/usr/bin/bash -ex

AGENT_LOG="/var/log/neutron/f5-openstack-agent.log"
if [[ -f ${AGENT_LOG} ]]; then
	owner="$(stat --format '%U' ${AGENT_LOG})"
	id neutron >/dev/null 2>&1
	has_user_neutron=$?
	if [[ ${owner} == 'root' && ${has_user_neutron} == 0 ]]; then
		chown neutron:neutron ${AGENT_LOG}
	fi
fi
