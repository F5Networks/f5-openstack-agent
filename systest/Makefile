.PHONY: all systest functest disconnected_service disconnected_service-setup \
disconnected_service-install disconnected_service-run \
disconnected_service-teardown

PROJECT := f5-openstack-agent
repo := https://github.com/F5Networks/$(PROJECT).git
ssh_conf := testenv_symbols/testenv_ssh_config

# - <nearest reachable tag>-<num commits since>-g<abbreviated commit id>
version := $(shell git describe --long)
timestamp := $(shell date +"%Y%m%d-%H%M%S")
RESULTSDIR := test_results/$(PROJECT)
disconnected_results := $(RESULTSDIR)/disconnected
unit_results := $(RESULTSDIR)/unit

unit_session := unit_$(version)_$(timestamp)
tempest_session := tempest_$(version)_$(timestamp)
disconnected_session := disconnected_$(version)_$(timestamp)

branch := $(shell git rev-parse --abbrev-ref HEAD)
testenv_config := os-agent-disconnected.testenv.yaml

functest:
	$(MAKE) -j -C . functest_all

functest_all: disconnected_service 

disconnected_service:
	@echo "automated functional tests..."
	$(MAKE) -C . disconnected_service-setup
	$(MAKE) -C . disconnected_service-install
	@echo "running unittests tests ..."
	$(MAKE) -C . unittest-run
	@echo "unittests done..."
	$(MAKE) -C . disconnected_service-run
	$(MAKE) -C . disconnected_service-teardown

unittest-run:
	scp -F $(ssh_conf) ./scripts/run_unittests.sh bastion:~/
	ssh -tF $(ssh_conf) bastion "~/run_unittests.sh $(unit_session)"

disconnected_service-setup:
	@echo "setting up functional test environment ..."
	testenv create --name $(disconnected_session) --config $(testenv_config)
	sleep 360

disconnected_service-install:
	@echo "installing system tests ..."
	scp -rp -F $(ssh_conf) testenv_symbols/ bastion:~/
	scp -F $(ssh_conf) ./scripts/install_systests.sh bastion:~/
	ssh -AF $(ssh_conf) bastion "~/install_systests.sh $(repo) $(branch)"

disconnected_service-run:
	@echo "running disconnected tests ..."
	scp -F $(ssh_conf) ./scripts/run_neutronlesstests.sh bastion:~/
	ssh -tF $(ssh_conf) bastion \
		"~/run_neutronlesstests.sh $(disconnected_session)" || true

disconnected_service-teardown:
	@echo "downloading functional test results ..."
	if [ ! -e $(disconnected_results) ]; then mkdir -p $(disconnected_results); fi
	if [ ! -e $(unit_results) ]; then mkdir -p $(unit_results); fi
	scp -rp -F $(ssh_conf) \
		bastion:~/test_results/$(disconnected_session)/* $(disconnected_results) || true
	scp -rp -F $(ssh_conf) \
		bastion:~/test_results/$(unit_session)/* $(unit_results) || true
	testenv delete --name $(disconnected_session) --config $(testenv_config) || true
