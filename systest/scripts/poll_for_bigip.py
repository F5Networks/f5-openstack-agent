import json
import sys
import time


from f5.bigip import ManagementRoot
from icontrol.exceptions import iControlUnexpectedHTTPError

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SYMBOLS = json.load(open('testenv_symbols/testenv_symbols.json'))
count = 0
while True:
    print("polling for mgmt/tm/sys availability: %s" % count)
    try:
        ManagementRoot(SYMBOLS["bigip_mgmt_ip_public"], "admin", "admin")
        break
    except iControlUnexpectedHTTPError:
        pass
    time.sleep(1)
    count += 1
    if count > 300:
        sys.exit(2)
