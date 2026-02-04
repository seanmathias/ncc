# General
## Device Type/Driver
### Unknown Device Types/Device Type Discovery
Napalm requires specifying the device type when dispatching a job or connecting
to it. It would be nice to be able to not have to do this, or to have a means 
of doing device type discovery for unknown devices or when the device type is 
not known in advance.

## Device Inventory Database
Store device inventory in database and select tqargets from inventory. 

Inventory database can eventually be built from network discovery.

## Secure Credentials
1. Use Environment Variables
```
python

import os
import json

# Load inventory and replace passwords
with open('devices.json') as f:
    inventory = json.load(f)

for device in inventory:
    # Use environment variables for passwords
    device['password'] = os.getenv(f"{device['hostname']}_PASSWORD")
```

2. Use SSH Keys (where supported)
For Juniper and Linux-based devices:
```
json

{
    "hostname": "juniper-mx.example.com",
    "device_type": "junos",
    "username": "admin",
    "password": "",
    "optional_args": {
        "key_file": "/home/user/.ssh/id_rsa"
    }
}
```

3. Encrypt Inventory File
```
bash

# Using Ansible Vault
ansible-vault encrypt devices.json

# Using GPG
gpg -c devices.json
```

4. Restrict File Permissions
```
bash

chmod 600 devices.json
chmod 700 backups/
```

## Project Name
Rename to ncx - Network Command Executor

## CLI arguments
Refactor so command and subcommands come first with all arguments following 
rather than `command --arguments subcommand --subcommand-args`

# Backup
## Job summary
Change from simple table of devices to back up by device type to provide a summary of parameters, etc.

# Discovery


# Automation
## Snapshot
Automate gathering state of devices before and after changes to use as a basis of comparison

Can be coupled with configuration archival prior to changes to have a baseline of network state 
and known good configurations to fall back to in the event of anomalous behavior or outcomes.