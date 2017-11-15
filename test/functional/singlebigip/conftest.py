import pytest

from f5.bigip import ManagementRoot
from pytest import symbols

@pytest.fixture(scope="module")
def mgmt_root ():
    m_obj = ManagementRoot(symbols.bigip_mgmt_ip_public, symbols.bigip_username, symbols.bigip_password)
    m_obj._meta_data['device_name'] = 'bigip1'
    return m_obj
