.PHONY: all unit systest functest disconnected_service disconnected_service-setup \
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
RESULTSDIR := $(MAKEFILE_DIR)/test_results/$(PROJECT)

unit_session := unit_$(version)_$(timestamp)
tempest_session := tempest_$(version)_$(timestamp)
disconnected_session := disconnected_$(version)_$(timestamp)

unit_results := $(RESULTSDIR)/$(unit_session)
disconnected_results := $(RESULTSDIR)/$(disconnected_session)

branch := $(shell git rev-parse --abbrev-ref HEAD)
testenv_config := bigip.testenv.yaml

unit:
	cd $(MAKEFILE_DIR)/../
	tox -e unit-buildbot -- \
		--exclude incomplete no_regression \
		--autolog-outputdir $(unit_results) \
		--autolog-session $(unit_session) \

functest:
	$(MAKE) -j -C . functest_all

functest_all:
	@echo "automated functional tests..."
	$(MAKE) -C . disconnected_service

disconnected_service:
	$(MAKE) -C . disconnected_service-setup
	$(MAKE) -C . disconnected_service-run
	$(MAKE) -C . disconnected_service-teardown

disconnected_service-setup:
	@echo "setting up functional test environment ..."
	pip install git+ssh://git@bldr-git.int.lineratesystems.com/tools/testenv.git
	pip install git+ssh://git@bldr-git.int.lineratesystems.com/velcro/systest-common.git
	testenv create base
	testenv create --name $(disconnected_session) --config $(testenv_config)

disconnected_service-run:
	@echo "running disconnected tests ..."
	tox -e functest-buildbot -- \
		--symbols $(MAKEFILE_DIR)/testenv_symbols/testenv_symbols.json \
		--exclude incomplete no_regression \
		--autolog-outputdir $(disconnected_results) \
		--autolog-session $(disconnected_session) \
		neutronless/disconnected_service || $(MAKE) -C . disconnected_service-teardown

disconnected_service-teardown:
	@echo "tearing down functional test environment..."
	if [ ! -e $(disconnected_results) ]; then mkdir -p $(disconnected_results); fi
	if [ ! -e $(unit_results) ]; then mkdir -p $(unit_results); fi
	testenv delete --name $(disconnected_session) --config $(testenv_config)
