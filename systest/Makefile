.PHONY: all systest functest disconnected_service disconnected_service-setup \
disconnected_service-install disconnected_service-run \
disconnected_service-teardown

repo := https://github.com/zancas/f5-openstack-agent.git
registry := docker-registry.pdbld.f5net.com
namespace := openstack
ssh_conf := testenv_symbols/testenv_ssh_config

# - <nearest reachable tag>-<num commits since>-g<abbreviated commit id>
version := $(shell git describe --long)
export version
timestamp := $(shell date +"%Y%m%d-%H%M%S")
export timestamp
results_dir := test_results/proxy/proxy-$(version)-$(timestamp)

func_session := os-agent-neutronless_$(version)

current_branch := $(shell git rev-parse --abbrev-ref HEAD)

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
	ssh -tF $(ssh_conf) bastion "~/run_unittests.sh $(func_session)"

disconnected_service-setup:
	@echo "setting up functional test environment ..."
	testenv create --name os-agent-neutronless \
		--config os-agent-neutronless.testenv.yaml
	echo `date "+%s"`
	sleep 360
	echo `date "+%s"`

disconnected_service-install:
	@echo "installing system tests ..."
	scp -rp -F $(ssh_conf) testenv_symbols/ bastion:~/
	scp -F $(ssh_conf) ./scripts/install_systests.sh bastion:~/
	ssh -AF $(ssh_conf) bastion "~/install_systests.sh $(repo) $(current_branch)"

disconnected_service-run:
	@echo "running neutronless tests ..."
	scp -F $(ssh_conf) ./scripts/run_neutronlesstests.sh bastion:~/
	ssh -tF $(ssh_conf) bastion \
		"~/run_neutronlesstests.sh $(func_session)" \
		|| true

disconnected_service-teardown:
	@echo "downloading functional test results ..."
	if [ ! -e $(results_dir) ]; then mkdir -p $(results_dir); fi
	scp -rp -F $(ssh_conf) \
		bastion:~/test_results/$(func_session)/* $(results_dir)/ \
		|| true

	@echo "tearing down functional test environment ..."
	testenv delete --name os-agent-neutronless || true
