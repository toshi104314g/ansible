# Rocky Linux 9 / Ubuntu 26.04 UTM provisioning

`create-linux-utm` combines the existing Rocky Linux 9 and Ubuntu 26.04 UTM workflows. The OS-specific playbooks remain in their original directories and are not changed by this unified playbook.

Each inventory host selects its operating system and UTM template with `utm_os` and `utm_template_name`. See [`inventory_linux_utm.example.yml`](../inventory/inventory_linux_utm.example.yml) for a mixed-OS inventory example. Copy it to a private inventory file and adjust names and addresses; private inventories are ignored by Git.

Supported `utm_os` values:

- `rocky9`: SSH as `root`; configures static IPv4 with NetworkManager while retaining IPv6 SLAAC.
- `ubuntu26`: SSH as `toshiyuki` with passwordless `sudo -n`; configures static IPv4 with Netplan while retaining IPv6 SLAAC.

The following network settings are inherited from the inventory's `all.vars` or the host's groups: `utm_network_connection`, `utm_global_ipv6_prefix`, `utm_ipv4_prefix_length`, `utm_ipv4_gateway`, and `utm_ipv4_dns_servers`. `utm_provision` may be set per host or inherited from a group and must be `clone` or `existing`. Existing guests additionally require `utm_ssh_alias`.

Run commands from the repository root and always select exactly one inventory with `-i`:

```sh
# Create/configure cloned VMs and update /etc/hosts
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux_utm.yml \
  --ask-become-pass \
  create-linux-utm/create-linux-utm.yml

# Create/configure VMs without changing /etc/hosts
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux_utm.yml \
  create-linux-utm/create-linux-utm.yml \
  --skip-tags hosts_file

# Update only the selected inventory's /etc/hosts entries
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux_utm.yml \
  --ask-become-pass \
  create-linux-utm/create-linux-utm.yml \
  --tags hosts_file

# Delete the selected inventory VMs (requires typing DELETE)
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux_utm.yml \
  create-linux-utm/create-linux-utm.yml \
  --tags delete \
  --skip-tags remove_hosts_file
```

Before cloning, each selected template must already exist in UTM and be stopped. The playbook does not start or modify templates. Templates must be prepared for their corresponding OS as described in the Rocky Linux and Ubuntu playbook READMEs. For Ubuntu templates, the `toshiyuki` account must have passwordless sudo, SSH key authentication, QEMU Guest Agent, and the Netplan DHCPv4/SLAAC baseline configured. For Rocky templates, root SSH and QEMU Guest Agent must be available.

Deletion protects every `utm_template_name` specified by the inventory. The `remove_hosts_file` tag controls only removal of `/etc/hosts` entries and is independent of the VM deletion confirmation.
