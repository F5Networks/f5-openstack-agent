.PHONY: all clean pre-build unit systest functest disconnected_service \
disconnected_service-setup \
disconnected_service-install disconnected_service-run \
disconnected_service-teardown

PROJECT := f5-openstack-agent
repo := https://github.com/F5Networks/$(PROJECT).git
ssh_conf := testenv_symbols/testenv_ssh_config

MAKEFILE_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))

# - <nearest reachable tag>-<num commits since>-g<abbreviated commit id>
version := $(shell git describe --long)
timestamp ?= $(shell date +"%Y%m%d-%H%M%S")
export timestamp   # Only eval timestamp in the top make.
branch := $(shell git rev-parse --abbrev-ref HEAD)

RESULTSDIR := $(MAKEFILE_DIR)/test_results/$(PROJECT)/$(PROJECT)_$(branch)

unit_session := unit_$(version)_$(timestamp)
disconnected_session := disconnected_$(version)_$(timestamp)


testenv_config := bigip.testenv.yaml

VENV := buildbot
VENV_ACTIVATE := $(MAKEFILE_DIR)/$(VENV)/bin/activate

# Before we run any tests we need a virtualenv and a few packages
pre-build:
	sudo apt-get update; \
	sudo apt-get install -y libssl-dev; \
	sudo apt-get install -y libffi-dev; \
	sudo -H pip install tox; \
	sudo -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/testenv.git; \
	sudo -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/velcro/systest-common.git; \
	sudo -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-meta.git; \
	sudo -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-autolog.git; \
	sudo -H pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/pytest-symbols.git;

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
	tox -e functest --sitepackage -- \
		--symbols $(MAKEFILE_DIR)/testenv_symbols/testenv_symbols.json \
		--exclude incomplete no_regression \
		--autolog-outputdir $(RESULTSDIR) \
		--autolog-session $(disconnected_session) \
		neutronless/disconnected_service || $(MAKE) -C . disconnected_service-teardown

disconnected_service-teardown:
	@echo "tearing down functional test environment..."
	if [ ! -e $(disconnected_results) ]; then mkdir -p $(disconnected_results); fi
	if [ ! -e $(unit_results) ]; then mkdir -p $(unit_results); fi
	testenv delete --name $(disconnected_session) --config $(testenv_config)

# Remove the buildbot venv directory and any tox venvs we made
clean:
	-rm -rf $(MAKEFILE_DIR)/../.tox/functest-buildbot
	-rm -rf $(MAKEFILE_DIR)/../.tox/unit-buildbot
