# Command

## masquerade_mac

### Usage:

The command `masquerade_mac` can generate masquerade MAC based on Bigip Base MAC.


The command follows the procedure of document [K3523](https://support.f5.com/csp/article/K3523) to generate masquerade MAC.

Please read [K3523](https://support.f5.com/csp/article/K3523) for more details.

```bash
[root@ci ~]# masquerade_mac -h
masquerade_mac -i <bigip_ip> -u <admin_username> -p <admin_password>
```

### Required parameters:

* -i: <font color='orange'>**Active BigIP**</font> management IP.
* -u: BigIP admin username.
* -p: BigIP admin password.

### Example:

```bash
[root@ci ~]# masquerade_mac -i 192.110.80.81 -u admin -p admin_password
Base MAC is fa:16:3e:16:34:38

Masquerade MAC is fa:16:3e:16:34:38

```
