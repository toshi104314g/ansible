# Rocky Linux 9 / Ubuntu 26.04 UTM provisioning

`create-linux-utm` combines the existing Rocky Linux 9 and Ubuntu 26.04 UTM workflows. The OS-specific playbooks remain in their original directories and are not changed by this unified playbook.

Each inventory host selects its operating system and UTM template with `utm_os` and `utm_template_name`. See [`inventory_linux_utm.example.yml`](../inventory/inventory_linux_utm.example.yml) for a mixed-OS inventory example. Copy it to a private inventory file and adjust names and addresses; private inventories are ignored by Git.

Supported `utm_os` values:

- `rocky9`: provisions through root, then configures the shared `ansible-user` account with passwordless sudo; configures static IPv4 with NetworkManager while retaining IPv6 SLAAC.
- `ubuntu26`: provisions through the template's `toshiyuki` account, then configures the same `ansible-user` account and public key; configures static IPv4 with Netplan while retaining IPv6 SLAAC.

Both guest OSes use the public key matching the existing `~/.ssh/id_ed25519` provisioning key. Set `ansible_user: ansible-user` and `ansible_ssh_private_key_file: ~/.ssh/id_ed25519` in the inventory for subsequent Ansible commands.
The existing-guest configuration path also adds this account using its current OS-specific SSH account as a one-time bootstrap.

The guest interface layout and UTM host-side bridge interfaces are defined once in [`inventory/group_vars/all.yml`](../inventory/group_vars/all.yml): management uses host `en7` and guest `enp0s1`; LAB and DMZ use host `vlan0`/`vlan1` and the guest's first/second additional NIC. The KVM wrapper copies the same inventory group variables to its remote execution host.

Per-VM IP addresses and guest settings stay in the selected inventory. `utm_global_ipv6_prefix`, `utm_ipv4_prefix_length`, `utm_ipv4_gateway`, and `utm_ipv4_dns_servers` may be inherited from the inventory's `all.vars` or host groups. `utm_network_connection` remains accepted as a legacy alias for the management guest interface; new inventories should omit it and use the shared topology mapping. `utm_provision` may be set per host or inherited from a group and must be `clone` or `existing`. Existing guests additionally require `utm_ssh_alias`.

Before a clone is started, its UTM `config.plist` and UTM's in-memory configuration are updated using the host-interface mapping in the shared topology. A LAB address adds a guest interface on `vlan0`; a DMZ address adds one on `vlan1`. DMZ-only guests therefore use their first additional NIC, without a dummy LAB interface. Guests with both addresses use their first additional NIC for LAB and their second for DMZ. Running VMs are not modified; if their bridge configuration needs changes, the playbook reports an error instead.

After the management interface is configured, provisioning also configures each optional LAB/DMZ address on its corresponding guest interface. Rocky guests use NetworkManager profiles; Ubuntu guests use Netplan. Both networks may be configured on one guest. Existing UTM guests must already have the corresponding bridged interfaces. The LAB/DMZ interfaces do not install default routes; the management interface retains `utm_ipv4_gateway`, which must be `192.168.10.1` for hosts using either network.

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

For non-interactive deletion, explicitly confirm with `-e utm_delete_confirmation_input=DELETE`; otherwise the playbook prompts for `DELETE`.

During creation, UTM clones are provisioned concurrently, each as an independent inventory host. Ansible's `forks` setting limits the number running at once; use `-f` to override it for a run (for example, `-f 8`). Each guest uses a separate SSH known-hosts file during provisioning to avoid concurrent writes to the shared file.

A guest is skipped with a warning if its UTM VM name differs from its inventory hostname, or if its current guest hostname is neither the inventory hostname nor a clean template default. Other UTM guests continue provisioning. A guest that fails another provisioning task is also reported as skipped, and is excluded from the hosts-file update.
