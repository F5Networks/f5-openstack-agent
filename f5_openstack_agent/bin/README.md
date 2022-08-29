# Command

## masquerade_mac

### Usage:

```bash
[root@ci ~]# masquerade_mac -h
masquerade -i <bigip_ip> -u <admin_username> -p <admin_password>
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
