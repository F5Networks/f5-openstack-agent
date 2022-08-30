# coding=utf-8

import getopt
import json
import requests
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import sys

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def hex_binary(value):
    int_value = int(value, base=16)
    bin_value = bin(int_value)[2:].zfill(8)
    return bin_value


def binary_hex(value):
    int_value = int(value, base=2)
    hex_value = hex(int_value)[2:].zfill(2)
    return hex_value


def gen_masquerade_mac(mac):
    temp_mac = mac.split(":")

    first_byte = temp_mac[0]
    binary = hex_binary(first_byte)
    binary = binary[:6] + "1" + binary[-1]
    hexa = binary_hex(binary)

    temp_mac = [hexa] + temp_mac[1:]
    masquerade_mac = ":".join(temp_mac)
    return masquerade_mac


def input(inputs):

    value = dict()

    try:
        opts, args = getopt.getopt(
            inputs, "hi:u:p:", ["ip=", "user=", "password="]
        )
    except getopt.GetoptError:
        print(
            "masquerade_mac -i <bigip_ip>" +
            " -u <admin_username> -p <admin_password>"
        )
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            print(
                "masquerade_mac -i <bigip_ip>" +
                " -u <admin_username> -p <admin_password>"
            )
            sys.exit()
        elif opt in ("-i", "--ip"):
            value["ip"] = arg
        elif opt in ("-u", "--user"):
            value["user"] = arg
        elif opt in ("-p", "--password"):
            value["password"] = arg

    return value


def get_base_mac(inputs):
    url = "https://" + inputs["ip"] + "/mgmt/tm/util/bash"
    payload = {
        "command": "run",
        "utilCmdArgs": "-c \"tmsh show sys hardware" +
        " field-fmt | grep base-mac\""
    }
    auth = HTTPBasicAuth(inputs["user"], inputs["password"])
    verify = False

    resp = requests.post(url, json=payload, verify=verify, auth=auth)
    data = json.loads(resp.content)
    base_mac = data['commandResult'].split()[1]

    return base_mac


def main():
    value = input(sys.argv[1:])
    base_mac = get_base_mac(value)
    print("Base MAC is %s\n" % base_mac)
    mas_mac = gen_masquerade_mac(base_mac)
    print("Masquerade MAC is %s\n" % mas_mac)
