.PHONY: all clean pre-build unit systest functest disconnected_service \
disconnected_service-setup \
disconnected_service-install disconnected_service-run \
disconnected_service-teardown singlebigip \
singlebigip-setup \
singlebigip-install singlebigip-run \
singlebigip-teardown

PROJECT := f5-openstack-agent
repo := https://github.com/F5Networks/$(PROJECT).git
ssh_conf := testenv_symbols/testenv_ssh_config

MAKEFILE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR := $(shell dirname $(realpath $(MAKEFILE_DIR)))

# - <nearest reachable tag>-<num commits since>-g<abbreviated commit id>
version := $(shell git describe --long)
timestamp ?= $(shell date +"%Y%m%d-%H%M%S")
export timestamp   # Only eval timestamp in the top make.
branch := $(shell git rev-parse --abbrev-ref HEAD)

RESULTSDIR := $(MAKEFILE_DIR)/test_results/$(PROJECT)/$(PROJECT)_$(branch)

unit_session := unit_$(version)_$(timestamp)
unit_results := $(RESULTSDIR)/$(unit_session)
disconnected_session := disconnected_$(version)_$(timestamp)
disconnected_results := $(RESULTSDIR)/$(disconnected_session)
singlebigip_session := singlebigip_$(version)_$(timestamp)
singlebigip_results := $(RESULTSDIR)/$(singlebigip_session)


testenv_config := bigip.testenv.yaml

VENV := buildbot
VENV_ACTIVATE := $(MAKEFILE_DIR)/$(VENV)/bin/activate

# Before we run any tests we need a virtualenv and a few packages
pre-build:
	sudo -E apt-get update; \
	sudo -E apt-get install -y libssl-dev; \
	sudo -E apt-get install -y libffi-dev; \
	sudo -E -H pip install --upgrade pip; \
	sudo -E -H pip install tox; \
	sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/testenv.git; \
	sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/velcro/systest-common.git; \
	sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-meta.git; \
	sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-autolog.git; \
	sudo -E -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-symbols.git;

unit: pre-build
	cd $(MAKEFILE_DIR)/../; \
	tox -e unit --sitepackages -- \
		--exclude incomplete no_regression \
		--autolog-outputdir $(RESULTSDIR) \
		--autolog-session $(unit_session) \

functest:
	$(MAKE) -C . unit
	$(MAKE) -j -C . functest_all

functest_all:
	@echo "automated functional tests..."
	$(MAKE) -C . disconnected_service
	$(MAKE) -C . singlebigip

disconnected_service:
	$(MAKE) -C . disconnected_service-setup
	$(MAKE) -C . disconnected_service-run
	$(MAKE) -C . disconnected_service-teardown

disconnected_service-setup: pre-build
	@echo "setting up functional test environment ..."
	testenv create base; \
	testenv create --name $(disconnected_session) --config $(testenv_config); \

disconnected_service-run: pre-build
	@echo "running disconnected tests ..."
	tox -e disconnected_service --sitepackage -- \
		--symbols $(MAKEFILE_DIR)/testenv_symbols/testenv_symbols.json \
		--exclude incomplete no_regression \
		--autolog-outputdir $(RESULTSDIR) \
		--autolog-session $(disconnected_session) \
		$(PROJECT_DIR)/test/functional/neutronless/disconnected_service || $(MAKE) -C . disconnected_service-teardown

disconnected_service-teardown:
	@echo "tearing down functional test environment..."
	if [ ! -e $(disconnected_results) ]; then mkdir -p $(disconnected_results); fi
	if [ ! -e $(unit_results) ]; then mkdir -p $(unit_results); fi
	testenv delete --name $(disconnected_session) --config $(testenv_config)

singlebigip:
	$(MAKE) -C . singlebigip-setup
	$(MAKE) -C . singlebigip-run
	$(MAKE) -C . singlebigip-teardown

singlebigip-setup: pre-build
	@echo "setting up singlebigip test environment ..."
	testenv create base; \
	testenv create --name singlebigip --config $(testenv_config); \

singlebigip-run: pre-build
	@echo "running singlebigip tests ..."
	tox -e singlebigip --sitepackage -- \
		--symbols $(MAKEFILE_DIR)/testenv_symbols/testenv_symbols.json \
		--exclude incomplete no_regression \
		--autolog-outputdir $(RESULTSDIR) \
		--autolog-session $(singlebigip_session) \
		$(PROJECT_DIR)/test/functional/singlebigip || $(MAKE) -C . singlebigip-teardown

singlebigip-teardown:
	@echo "tearing down singlebigip test environment..."
	if [ ! -e $(singlebigip_results) ]; then mkdir -p $(singlebigip_results); fi
	if [ ! -e $(unit_results) ]; then mkdir -p $(unit_results); fi
	testenv delete --name $(singlebigip_session) --config $(testenv_config)

# Remove the buildbot venv directory and any tox venvs we made
clean:
	-rm -rf $(MAKEFILE_DIR)/../.tox/functest-buildbot
	-rm -rf $(MAKEFILE_DIR)/../.tox/unit-buildbot
