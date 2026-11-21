# Unified Linux UTM and KVM wrapper

`create-linux.yml` runs the UTM workflow on the Mac and the KVM workflow on the Ubuntu KVM controller concurrently from one inventory. Hosts with `utm_vm_name` are managed by UTM; hosts with `kvm_vm_name` are managed by KVM. Keep the two host sets in separate groups, and give every guest a unique inventory name and IPv4 address. See [`inventory_linux.example.yml`](../inventory/inventory_linux.example.yml) for an example.

Copy the example to the ignored `inventory/inventory_linux.yml` and customize the VM names, templates, network settings, and unique addresses. The wrapper validates that every host belongs to exactly one backend and that the UTM and KVM guests do not share IPv4 addresses.

Run from the repository root on the Mac:

```sh
# Create/configure all UTM and KVM guests
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/create-linux.yml \
  -b -K

# Create/configure only the inventory host named files1
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/create-linux.yml \
  -e hostname=files1 \
  -b -K

# Create/configure multiple inventory hosts
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/create-linux.yml \
  -e hostname=files1,ldap1 \
  -b -K

# Delete all selected UTM and KVM guests
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/create-linux.yml \
  --tags delete \
  -b -K
```

`-e hostname=<inventory_hostname>[,<inventory_hostname>...]` limits creation, deletion, and hosts-file updates to the listed inventory hosts. Separate names with commas; spaces around names are ignored. Every name must exist in the inventory and be unique. If omitted, the full inventory is used as before.

KVM guests provisioned with temporary management networking may omit `ansible_host` when temporary management and private-network DHCP are configured. Their temporary addresses are selected during provisioning and are not added to `/etc/hosts`.

Deletion asks for `DELETE` in each backend workflow before removing its guests. For non-interactive deletion, provide both `-e utm_delete_confirmation_input=DELETE` and `-e kvm_wrapper_delete_confirmation_input=DELETE`. On KVM, Mac `/etc/hosts` entries are removed by default; Ubuntu KVM controller entries are changed only when `ubuntu_hosts_file` is also selected. UTM guests update the Mac `/etc/hosts` file as part of the UTM workflow. The `-b -K` options provide the Mac sudo password for these hosts-file changes.

The KVM workflow uses the SSH config alias `ubuntu` by default; override it with `-e kvm_controller_ssh_alias=<alias>`. Ubuntu's sudo password is requested only when using the optional `ubuntu_hosts_file` tag.

## Start stopped VMs

To start only the VMs named by a selected UTM/KVM inventory, run:

```sh
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/start-linux.yml
```

The playbook starts UTM VMs whose status is `stopped` and KVM domains whose state is `shut off`; VMs that are already running are left unchanged. It verifies the final state and fails for missing VMs or states it does not explicitly support. The KVM controller SSH alias defaults to `ubuntu` and can be overridden with `-e kvm_controller_ssh_alias=<alias>`. This operation does not change guest configuration or hosts files.

VM inventories contain per-guest identity, IP addresses, and OS/template choices. Shared host-to-guest interface mappings are defined in [`inventory/group_vars/all.yml`](../inventory/group_vars/all.yml) and loaded for inventories stored beside that `group_vars` directory. UTM uses Mac `en7` for management, `vlan0` for LAB, and `vlan1` for DMZ; the guest interface slots are configured there as well. A legacy `utm_network_connection` value is still accepted, but new inventories should omit it. KVM defaults to management bridge `br0` and LAB/DMZ bridges `br100`/`br200`; inventories can still select a libvirt network or another management bridge where needed. Optional `lab_ipv4_address` and `dmz_ipv4_address` settings request those logical networks and their guest addresses. When either optional network is configured, the management default gateway must be `192.168.10.1`; LAB/DMZ interfaces do not add default routes. Refer to the existing [UTM](../create-linux-utm/README.md) and [KVM](../create-linux-kvm-remote/README.md) documentation for template and controller prerequisites.

The LAB/DMZ address configuration is part of UTM/KVM provisioning; do not run the standalone `tmpbooks/init-lab-network.yml` afterward for those guests.

UTM and KVM clones are provisioned concurrently per backend, while the two backends run concurrently. A VM name that differs from its inventory hostname is skipped with a warning. A clone whose current guest hostname does not match the inventory is also skipped before guest configuration. Other clones and the other backend continue; failed guests are excluded from the Mac and KVM-controller hosts-file updates. The unified wrapper updates the Mac hosts file once both backend workflows finish.

Before creating a clone, the playbooks check the applicable `/etc/hosts` files for the guest IPv4 address. If that address is associated with a different hostname on the Mac (UTM and all guests) or on the Ubuntu KVM controller (KVM guests), only that clone is skipped with a warning.

New clones on either OS are configured with the shared `ansible-user` account, the same public key as the provisioning account's `~/.ssh/id_ed25519`, and passwordless sudo. Set `ansible_user: ansible-user` and `ansible_ssh_private_key_file` to that key in the inventory to use normal inventory-based Ansible commands across Rocky and Ubuntu.
