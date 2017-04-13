From ubuntu:16.04

# To build this, do docker build -t vcmp_tests --build-arg BRANCH=liberty --build-arg AGENT_REPO_FORK=F5Networks --build-arg AGENT_TEST_BRANCH=liberty -f Dockerfile .
# Then do docker run vcmp_tests

ARG BRANCH
ARG AGENT_REPO_FORK
ARG AGENT_TEST_BRANCH
RUN apt-get -y update
RUN apt-get install -y git
RUN apt-get install -y vim
RUN apt-get install -y python-pip
RUN apt-get install -y python-dev
RUN apt-get install -y build-essential
RUN apt-get install -y libssl-dev
RUN apt-get install -y libffi-dev
RUN pip install --upgrade pip
RUN pip install cryptography
RUN pip install hacking
RUN pip install mock
RUN pip install pytest
RUN pip install pytest-cov
RUN pip install paramiko
RUN pip install decorator
RUN pip install git+https://github.com/openstack/neutron@stable/$BRANCH
RUN pip install git+https://github.com/openstack/neutron-lbaas.git@stable/$BRANCH
RUN pip install git+https://github.com/openstack/oslo.log.git@stable/$BRANCH
RUN pip install git+https://github.com/F5Networks/f5-openstack-lbaasv2-driver.git@$BRANCH
RUN pip install git+https://github.com/F5Networks/pytest-symbols.git
# Enter your fork and branch below
RUN mkdir -p /root/devenv
RUN git clone -b $AGENT_TEST_BRANCH https://github.com/$AGENT_REPO_FORK/f5-openstack-agent.git /root/devenv/f5-openstack-agent
WORKDIR /root/devenv/f5-openstack-agent
RUN pip install -r /root/devenv/f5-openstack-agent/requirements.functest.txt
RUN py.test --cov=f5_openstack_agent f5_openstack_agent/
CMD py.test --symbols=/root/devenv/f5-openstack-agent/test/functional/neutronless/vcmp/common_service_handler_env.json -v /root/devenv/f5-openstack-agent/test/functional/neutronless/vcmp/test_vcmp.py
