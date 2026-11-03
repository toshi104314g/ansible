# Unified Linux UTM and KVM wrapper

`create-linux.yml` runs the existing UTM workflow on the Mac and the KVM workflow on the Ubuntu KVM controller from one inventory. Hosts with `utm_vm_name` are managed by UTM; hosts with `kvm_vm_name` are managed by KVM. Keep the two host sets in separate groups, and give every guest a unique inventory name and IPv4 address. See [`inventory_linux.example.yml`](../inventory/inventory_linux.example.yml) for an example.

Copy the example to the ignored `inventory/inventory_linux.yml` and customize the VM names, templates, network settings, and unique addresses. The wrapper validates that every host belongs to exactly one backend and that the UTM and KVM guests do not share IPv4 addresses.

Run from the repository root on the Mac:

```sh
# Create/configure all UTM and KVM guests
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/create-linux.yml \
  -b -K

# Delete all selected UTM and KVM guests
PATH="/opt/homebrew/bin:$PATH" ansible-playbook \
  -i inventory/inventory_linux.yml \
  create-linux/create-linux.yml \
  --tags delete \
  -b -K
```

Deletion asks for `DELETE` in each backend workflow before removing its guests. For non-interactive deletion, provide both `-e utm_delete_confirmation_input=DELETE` and `-e kvm_wrapper_delete_confirmation_input=DELETE`. On KVM, Mac `/etc/hosts` entries are removed by default; Ubuntu KVM controller entries are changed only when `ubuntu_hosts_file` is also selected. UTM guests update the Mac `/etc/hosts` file as part of the UTM workflow. The `-b -K` options provide the Mac sudo password for these hosts-file changes.

The KVM workflow uses the SSH config alias `ubuntu` by default; override it with `-e kvm_controller_ssh_alias=<alias>`. Ubuntu's sudo password is requested only when using the optional `ubuntu_hosts_file` tag.

UTM hosts require `utm_os`, `utm_template_name`, `utm_vm_name`, `utm_network_connection`, and the UTM IPv4/IPv6 settings. KVM hosts require `kvm_os`, `kvm_template_image`, `kvm_vm_name`, and the KVM network/storage settings. Refer to the existing [UTM](../create-linux-utm/README.md) and [KVM](../create-linux-kvm-remote/README.md) documentation for template and controller prerequisites.
