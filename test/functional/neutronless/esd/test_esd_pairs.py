# Copyright (c) 2016-2018, F5 Networks, Inc.
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
"""Tests of all (unordered) pairs of ESD tags."""
from .conftest import apply_validate_remove_validate


def test_esd_lbaas_stcp_lbaas_persist(track_bigip_cfg, ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_stcp_lbaas_cssl_profile(track_bigip_cfg,
                                           ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_persist_lbaas_sssl_profile(track_bigip_cfg,
                                              ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_irule_lbaas_ctcp(track_bigip_cfg,
                                    ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_fallback_persist_lbaas_persist(track_bigip_cfg,
                                                  ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_cssl_profile_lbaas_fallback_persist(track_bigip_cfg,
                                                       ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_cssl_profile_lbaas_sssl_profile(track_bigip_cfg,
                                                   ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_ctcp_lbaas_fallback_persist(track_bigip_cfg,
                                               ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_irule_lbaas_policy(track_bigip_cfg,
                                      demo_policy,
                                      ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_cssl_profile_lbaas_policy(track_bigip_cfg,
                                             demo_policy,
                                             ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_policy_lbaas_sssl_profile(track_bigip_cfg,
                                             demo_policy,
                                             ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_stcp_lbaas_policy(track_bigip_cfg,
                                     demo_policy,
                                     ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_irule_lbaas_fallback_persist(track_bigip_cfg,
                                                ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_stcp_lbaas_sssl_profile(track_bigip_cfg,
                                           ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_stcp_lbaas_irule(track_bigip_cfg,
                                    ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_irule_lbaas_sssl_profile(track_bigip_cfg,
                                            ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_policy_lbaas_persist(track_bigip_cfg,
                                        demo_policy,
                                        ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_ctcp_lbaas_sssl_profile(track_bigip_cfg,
                                           ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_cssl_profile_lbaas_ctcp(track_bigip_cfg,
                                           ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_stcp_lbaas_ctcp(track_bigip_cfg,
                                   ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_fallback_persist_lbaas_sssl_profile(track_bigip_cfg,
                                                       ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_fallback_persist_lbaas_policy(track_bigip_cfg,
                                                 demo_policy,
                                                 ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_ctcp_lbaas_policy(track_bigip_cfg,
                                     demo_policy,
                                     ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_irule_lbaas_persist(track_bigip_cfg,
                                       ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_cssl_profile_lbaas_persist(track_bigip_cfg,
                                              ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_stcp_lbaas_fallback_persist(track_bigip_cfg,
                                               ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_ctcp_lbaas_persist(track_bigip_cfg,
                                      ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)


def test_esd_lbaas_cssl_profile_lbaas_irule(track_bigip_cfg,
                                            ESD_Pairs_Experiment):
    """Validate application of a pair of tags."""
    apply_validate_remove_validate(ESD_Pairs_Experiment)
