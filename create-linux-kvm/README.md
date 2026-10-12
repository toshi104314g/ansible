# Rocky Linux 9 / Ubuntu 26.04 KVM provisioning

This playbook provisions Rocky Linux 9 and Ubuntu 26.04 guests on a Linux host using system libvirt/KVM. Run it on the Ubuntu KVM host itself; libvirt commands are executed locally through `qemu:///system`. It does not manage UTM.

Each host in the selected inventory must set:

- `kvm_os`: `rocky9` or `ubuntu26`
- `kvm_template_image`: a libvirt storage volume in the selected `kvm_storage_pool`
- `kvm_vm_name`: the libvirt domain name
- `ansible_host`: the guest's reserved static IPv4 address
- `kvm_provision`: `clone` or `existing`

Network and storage settings may be inherited from inventory groups or `all.vars`: specify exactly one of `kvm_network_name` (an active libvirt network) or `kvm_bridge_name` (an existing Linux bridge), along with `kvm_storage_pool`, `kvm_ipv4_prefix_length`, `kvm_ipv4_gateway`, and `kvm_ipv4_dns_servers`. The example inventory uses distinct template images for each OS. `rocky9` guests receive SSH access as `root`; `ubuntu26` guests receive the controller's public key for `toshiyuki`, configured with passwordless sudo. An optional `kvm_additional_ssh_public_key_file` adds another public key to cloned guests and to existing guests' `authorized_keys`. Private keys are never copied into guests or committed.

[`inventory_linux_kvm_br0.example.yml`](../inventory/inventory_linux_kvm_br0.example.yml) shows a mixed-OS inventory using addresses in `192.168.10.0/24`. It sets `kvm_bridge_name: br0`, so each VM interface connects directly to the host's existing Linux bridge—no intermediary libvirt network is created or required. The playbook verifies that the bridge exists and is up. Use addresses reserved for these VMs. Clone provisioning uses static IPv4 (`dhcp4: false`), enables DHCPv6 and IPv6 router advertisements (`dhcp6: true`, `accept-ra: true`), and configures Rocky guests to boot with SELinux disabled. Verification checks these settings and requires a dynamic global IPv6 address plus a default route learned from router advertisements. Ubuntu cloud images do not enable SELinux by default.

The controller requires `virsh`, `virt-install`, `qemu-img`, cloud-init-capable template images, the libvirt/KVM services, and permission to manage system libvirt and the selected storage pool. The templates should expose their primary virtio interface as `eth0` on Rocky Linux and `ens3` on Ubuntu so cloud-init can apply the IP configuration. The playbook creates and validates guest disks and domains, configures static IPv4 plus DHCPv6/router-advertisement IPv6 through cloud-init, installs and starts `qemu-guest-agent` through a virtio channel, waits for cloud-init and the guest agent to finish starting, and verifies SSH access, hostname, address, and Ubuntu NOPASSWD sudo. Templates and storage volumes are not modified.

## Prepare the KVM host

Install the KVM/libvirt tooling and enable system libvirt. Add the login user to the `libvirt` and `kvm` groups, then log out and back in so the new group memberships take effect. The account must be able to use `virsh -c qemu:///system` without sudo.

For inventories using `kvm_network_name`, prepare and activate that libvirt network before running the playbook. It must provide NAT/forwarding as needed. Keep static addresses outside the network's DHCP pool or reserve them for the corresponding guests. The sample uses a private NAT network with gateway `192.168.250.1`, static guests `.20` and `.21`, and a DHCP pool starting at `.100`:

```xml
<network>
  <name>ansible-kvm</name>
  <forward mode='nat'/>
  <bridge name='virbr-ansible' stp='on' delay='0'/>
  <ip address='192.168.250.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.250.100' end='192.168.250.254'/>
    </dhcp>
  </ip>
</network>
```

Save the XML on the KVM host, then define, start, and enable the network:

```sh
virsh net-define ansible-kvm.xml
virsh net-start ansible-kvm
virsh net-autostart ansible-kvm
```

Place one cloud-init-capable qcow2 image for each OS in the selected libvirt storage pool. For example, download the official Ubuntu 26.04 cloud image to a temporary location, then import it into the `default` pool as `ubuntu-26.04-cloudimg-amd64.img`. Do not use an installed VM's active disk as a template. Rocky images should be compatible with cloud-init and support root SSH keys.

Ensure the KVM controller has `~/.ssh/id_ed25519` and its matching `~/.ssh/id_ed25519.pub`; cloud-init installs the public key into the guest. The playbook uses a separate `~/.ssh/known_hosts.ansible-kvm` file.

## Run

Run from the repository root on the KVM host, selecting exactly one inventory:

```sh
# Create/configure the mixed-OS example VMs and update the Ubuntu hosts file
ansible-playbook \
  -i inventory/inventory_linux_kvm.example.yml \
  create-linux-kvm/create-linux-kvm.yml

# Optional: create/configure guests without changing the Ubuntu hosts file
ansible-playbook \
  -i inventory/inventory_linux_kvm.example.yml \
  create-linux-kvm/create-linux-kvm.yml \
  --skip-tags hosts_file

# Update only /etc/hosts (requires sudo/become authentication)
ansible-playbook \
  -i inventory/inventory_linux_kvm.example.yml \
  create-linux-kvm/create-linux-kvm.yml \
  --tags hosts_file \
  -K

# Delete VMs selected by the inventory and remove their /etc/hosts entries
# (requires sudo and typing DELETE)
ansible-playbook \
  -i inventory/inventory_linux_kvm.example.yml \
  create-linux-kvm/create-linux-kvm.yml \
  --tags delete \
  -K
```

Deletion stops and undefines only domains listed in the selected inventory, removes their attached storage, and removes their entries from the Ubuntu KVM controller's `/etc/hosts`. It does not remove template image volumes or the libvirt network. Review the inventory carefully before confirming deletion. If the controller user has passwordless sudo, `-K` is not required.
