# coding=utf-8
# Copyright (c) 2017,2018, F5 Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
"""These are tests of the ESD (Enhanced Services Definition) feature.

See conftest.py for the test logic, the setup procedure, and teardown.
ESDs are defined here:

https://devcentral.f5.com/articles/customizing-openstack-lbaasv2-using-enhanced-services-definitions-25681

The esd config used by ESD_Experiment:
    f5-openstack-agent/etc/neutron/services/f5/esd/demo.json
"""
from .conftest import apply_validate_remove_validate


def test_esd_two_irules(track_bigip_cfg, ESD_Experiment):
    """Refactor of an historical test of a 2 irule ESD."""
    apply_validate_remove_validate(ESD_Experiment)


# Single tag tests, each individual tag is tested.
def test_esd_lbaas_ctcp(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_stcp(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_cssl_profile(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_sssl_profile(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_irule(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_policy(track_bigip_cfg, demo_policy, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_persist(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_lbaas_fallback_persist(track_bigip_cfg, ESD_Experiment):
    """Test a single tag."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_full_8_tag_set(track_bigip_cfg, demo_policy, ESD_Experiment):
    """Test of a full tag set.  Tags specifics are historical."""
    apply_validate_remove_validate(ESD_Experiment)


def test_esd_issue_1047_basic(track_bigip_cfg, ESD_GRF_False_Experiment,
                              bigip):
    """Test behavior of l7policy removal as documented in github issue.

    https://github.com/F5Networks/f5-openstack-agent/issues/1047
    """
    test_virtual = bigip.bigip.tm.ltm.virtuals.get_collection()[0]
    test_virtual.modify(vlansEnabled=True)
    assert test_virtual.vlansEnabled is True
    tvvlans = test_virtual.__dict__.pop('vlans', "MISSING")
    assert tvvlans == "MISSING"
    apply_validate_remove_validate(ESD_GRF_False_Experiment)
    assert test_virtual.vlansEnabled is True
    tvvlans = test_virtual.__dict__.pop('vlans', "MISSING")
    assert tvvlans == "MISSING"
