.PHONY: all systest functest \
	functest-setup functest-install functest-run functest-teardown \

repo := https://github.com/F5Networks/f5-openstack-agent.git
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
	@echo "automated functional tests..."
	$(MAKE) -C . functest-setup && \
	$(MAKE) -C . functest-install && \
	$(MAKE) -C . functest-run && \
	$(MAKE) -C . functest-teardown

functest-setup:
	@echo "setting up functional test environment ..."
	testenv create --name os-agent-neutronless \
		--config os-agent-neutronless.testenv.yaml \
		|| true && \
	echo `date "+%s"` && \
	sleep 360 && \
	echo `date "+%s"`

functest-install:
	@echo "installing system tests ..."
	scp -rp -F $(ssh_conf) testenv_symbols/ bastion:~/
	scp -F $(ssh_conf) ./scripts/install_systests.sh bastion:~/
	ssh -AF $(ssh_conf) bastion "~/install_systests.sh $(repo) $(current_branch)"

unittest-run:
	scp -F $(ssh_conf) ./scripts/run_unittests.sh bastion:~/
	ssh -tF $(ssh_conf) bastion \
		"~/run_unittests.sh $(func_session)" \
		|| true

neutronless-run:
	scp -F $(ssh_conf) ./scripts/run_neutronlesstests.sh bastion:~/
	ssh -tF $(ssh_conf) bastion \
		"~/run_neutronlesstests.sh $(func_session)" \
		|| true

functest-run:
	@echo "running unittests tests ..."
	$(MAKE) -C . unittest-run
	@echo "unittests done..."
	@echo "running neutronless tests ..."
	$(MAKE) -C . neutronless-run
	@echo "neutronless done..."

functest-teardown:
	@echo "downloading functional test results ..."
	if [ ! -e $(results_dir) ]; then mkdir -p $(results_dir); fi
	scp -rp -F $(ssh_conf) \
		bastion:~/test_results/$(func_session)/* $(results_dir)/ \
		|| true

	@echo "tearing down functional test environment ..."
	testenv delete --name os-agent-neutronless || true
