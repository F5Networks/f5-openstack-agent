import pytest

from f5.bigip import ManagementRoot
from pytest import symbols


@pytest.fixture(scope="module")
def mgmt_root():
    bigip_quantname = \
        "host-{s.bigip_mgmt_ip}.openstacklocal".format(s=symbols)
    m_obj = ManagementRoot(
        symbols.bigip_mgmt_ip_public, symbols.bigip_username,
        symbols.bigip_password)
    m_obj._meta_data['device_name'] = bigip_quantname
    return m_obj
