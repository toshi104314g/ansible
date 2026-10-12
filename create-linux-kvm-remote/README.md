# Run the Linux KVM playbook from the Mac

This wrapper accepts a KVM guest inventory on the Mac, copies that inventory and the current `create-linux-kvm` playbook to the Ubuntu KVM host (the SSH alias `ubuntu` by default), and runs provisioning there. The Mac's `~/.ssh/id_ed25519.pub` is added to each guest in addition to the Ubuntu controller's key, so both the remote playbook and the Mac can access the guests. After successful provisioning, the wrapper adds the selected guest names and IPv4 addresses to the Mac's `/etc/hosts`.

The wrapper transfers only the public SSH key. The Mac private key remains on the Mac. The Ubuntu host must have Ansible, libvirt/KVM tools, the configured templates and storage pool, and permission to manage system libvirt. Its `~/ansible` checkout is not required because the current playbook is staged for each run.

Run from the repository root on the Mac, specifying exactly one guest inventory:

```sh
ansible-playbook \
  -i inventory/inventory_linux_kvm_br0.example.yml \
  create-linux-kvm-remote/create-linux-kvm-remote.yml \
  --ask-become-pass
```

`--ask-become-pass` is required to update the Mac's `/etc/hosts`. The wrapper uses the SSH config alias `ubuntu`; override it with `-e kvm_controller_ssh_alias=<alias>` if needed. The wrapper does not configure or copy the Mac private key to Ubuntu.
