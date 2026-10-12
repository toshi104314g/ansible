# Run the Linux KVM playbook from the Mac

This wrapper accepts a KVM guest inventory on the Mac, copies that inventory and the current `create-linux-kvm` playbook to the Ubuntu KVM host (the SSH alias `ubuntu` by default), and creates or deletes the selected guests there. When creating guests, the Mac's `~/.ssh/id_ed25519.pub` is added in addition to the Ubuntu controller's key, and the wrapper adds the selected guest names and IPv4 addresses to both Ubuntu's and the Mac's `/etc/hosts`. When deleting, the wrapper asks for `DELETE`, removes the inventory-selected guests on Ubuntu, then removes their entries from both hosts files.

The wrapper transfers only the public SSH key. The Mac private key remains on the Mac. The Ubuntu host must have Ansible, libvirt/KVM tools, the configured templates and storage pool, and permission to manage system libvirt. Its `~/ansible` checkout is not required because the current playbook is staged for each run.

Run from the repository root on the Mac, specifying exactly one guest inventory:

```sh
ansible-playbook \
  -i inventory/inventory_linux_kvm_br0.example.yml \
  create-linux-kvm-remote/create-linux-kvm-remote.yml
```

An invocation with no tags creates the guests. `--tags create` can also be specified explicitly. Run with `-b -K` to use the Mac's sudo password for Mac-side `/etc/hosts` changes. The Mac hosts entries are updated after successful creation, regardless of tag filters used for the Ubuntu hosts-file option. By default, guest creation does not modify Ubuntu's `/etc/hosts`, so it does not prompt for Ubuntu's sudo password. To also update Ubuntu's hosts file during creation, add the `ubuntu_hosts_file` tag; the wrapper will prompt for Ubuntu's sudo password only then:

```sh
ansible-playbook \
  -i inventory/inventory_linux_kvm_br0.example.yml \
  create-linux-kvm-remote/create-linux-kvm-remote.yml \
  --tags create,ubuntu_hosts_file \
  -b -K
```

Ubuntu's password is requested without echo, kept only in memory, and used only for the delegated Ubuntu hosts-file update. The wrapper uses the SSH config alias `ubuntu`; override it with `-e kvm_controller_ssh_alias=<alias>` if needed. The wrapper does not configure or copy the Mac private key to Ubuntu.

To delete the guests listed in the selected inventory, run the wrapper with the `delete` tag:

```sh
ansible-playbook \
  -i inventory/inventory_linux_kvm_br0.example.yml \
  create-linux-kvm-remote/create-linux-kvm-remote.yml \
  --tags delete \
  -b -K
```

The wrapper asks for `DELETE` and uses `-b -K` for the Mac's sudo password. By default, deletion removes guest domains and their attached clone storage on Ubuntu, then removes matching entries from the Mac's `/etc/hosts`; it does not prompt for Ubuntu's sudo password or change Ubuntu's hosts file. To also remove the matching Ubuntu entries, include the same `ubuntu_hosts_file` tag:

```sh
ansible-playbook \
  -i inventory/inventory_linux_kvm_br0.example.yml \
  create-linux-kvm-remote/create-linux-kvm-remote.yml \
  --tags delete,ubuntu_hosts_file \
  -b -K
```

Ubuntu's sudo password is prompted only when `ubuntu_hosts_file` is specified. Template images and libvirt networks are preserved.

For non-interactive runs, the destructive action can be explicitly confirmed with `-e kvm_wrapper_delete_confirmation_input=DELETE`. Without that exact value, the wrapper still asks for `DELETE` interactively.
