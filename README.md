# ncc
Network Command and Control, a toolbox of network utilities for network 
discovery and automation.

## Backup
Backup running configuration from target devices specified in devices file.

### Backup Directory
The configurations are collected from the target devices and stored in the 
specified directory, or in ncc_backups in the current directory if a 
directory is not specified.

Within the backup directory, a subdirectory is created for each target device 
and the configuration is stored in that directory in the form 
`host_YYYYMMDD_HHMMSS.cfg` which allows for storing multiple versions.

### Devices File
Backup target devices are specified in the devices file. This is a file in 
JSON format that must be provided to ncc to specify the target devices to backup.

The minimum required fields are the hostname and device_type. Usernames and 
passwords can be specified at the device level or specified at runtime as 
command line arguments. Device level credentials take precedence over those 
specified on the command line.

The general format is:
```
[
    {
        "hostname": "192.168.1.1",
        "device_type": "ios",
        "username": "admin",
        "password": "cisco_password",
        "optional_args": {}
    },
    {
        "hostname": "192.168.1.2",
        "device_type": "junos",
        "username": "admin",
        "password": "juniper_password",
        "optional_args": {}
    },
    {
        "hostname": "192.168.1.3",
        "device_type": "eos",
        "username": "admin",
        "password": "arista_password",
        "optional_args": {
            "transport": "https"
        }
    }
]
```
There are some optional arguments that vary by platform:

```
Cisco IOS
    "optional_args": {
        "secret": "enable_password",
        "port": 22
    }

    "optional_args": {
        "secret": "enable_password",    // Enable password
        "ssh_config_file": "~/.ssh/config"  // SSH config file
    }

NX-API
    "optional_args": {
        "transport": "https",
        "port": 443
    }

All
    "optional_args": {
        "port": 22,           // Custom SSH/API port
        "timeout": 60         // Connection timeout in seconds
    }

Arista
    "optional_args": {
        "transport": "https",   // or "http"
        "port": 443,           // or 80 for http
        "enable_password": "enable_secret"
    }

Juniper
    "optional_args": {
        "config_lock": false,      // Don't lock config
        "config_private": true,    // Use private candidate config
        "auto_probe": 30          // Probe timeout
    }
```

### Device Types Reference
Use these device_type values in your inventory:

| Vendor | Device Type     |   Description                 |
|--------|:----------------|:------------------------------|
|Cisco   |  ios            |   IOS devices (Catalyst, ISR) |
Cisco    |  nxos           |   Nexus switches (NX-API)     |
Cisco    |  nxos_ssh       |   Nexus switches (SSH)        |
Cisco    |  iosxr          |   IOS-XR devices (XML API)    |
Cisco    |  iosxr_netconf  |   IOS-XR devices (NETCONF)    |
Juniper  |  junos          |   JunOS devices (all)         |
Arista   |  eos            |   Arista EOS devices          |
