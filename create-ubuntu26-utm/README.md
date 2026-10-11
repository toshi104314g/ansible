# Ubuntu 26.04 VM management on UTM

このPlaybookはUbuntu 26.04 ServerのUTMテンプレートをInventoryに基づいてクローンし、ホスト名・静的IPv4・IPv6 SLAACを設定します。既存VMの設定、VM削除、Macの `/etc/hosts` 管理も行います。Rocky Linux用のPlaybookとは別ディレクトリ・別Inventoryです。

## このPlaybookでできること

- UTMテンプレートからInventoryに記載したVMを作成します。
- ゲストのホスト名と静的IPv4アドレスを設定し、IPv6 SLAACを維持します。
- `utm_provision: existing` の既存VMも、作り直さずに設定できます。
- `--tags delete` で選択したInventory内のUTM VMを削除し、同じInventoryに記載されたホスト名の `/etc/hosts` 行を削除します。
- 作成時はInventoryの `ansible_host` に基づいてMacの `/etc/hosts` を更新します。他Inventoryのホスト名は変更しません。

## PlaybookとInventoryの起動方法

リポジトリのルートディレクトリから実行します。既定のInventoryは [`inventory/inventory_ubuntu26.yml`](../inventory/inventory_ubuntu26.yml) です。別のInventoryで実行する場合は `-i` のパスを差し替えてください。Inventoryを指定しない実行や、複数Inventoryの指定は受け付けません。

```sh
# Ubuntu VMを作成・設定する（タグ省略時の既定動作）
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_ubuntu26.yml --ask-become-pass create-ubuntu26-utm/create-ubuntu26-utm.yml

# 作成・設定を明示
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_ubuntu26.yml --ask-become-pass create-ubuntu26-utm/create-ubuntu26-utm.yml --tags create

# 選択InventoryのVMを削除
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_ubuntu26.yml --ask-become-pass create-ubuntu26-utm/create-ubuntu26-utm.yml --tags delete
```

削除はUTM VMを完全に削除する操作です。削除Playbookは確認入力として `DELETE` を要求し、Inventoryに指定されたテンプレートVMは削除対象から保護します。`--ask-become-pass` はMacの `/etc/hosts` 更新・削除に使います。

VMだけを削除し、Macの `/etc/hosts` を変更しない場合は `--skip-tags remove_hosts_file` を追加します。この場合、Inventoryのホスト名エントリはMacの `/etc/hosts` に残ります。

VMの作成・設定だけを実行し、Macの `/etc/hosts` を変更しない場合は `--skip-tags hosts_file` を追加します。`/etc/hosts` のみを後から更新する場合は、次のコマンドを使います（Inventoryの検証後、VM作成・削除タスクは実行しません）。

```sh
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_ubuntu26.yml --ask-become-pass create-ubuntu26-utm/create-ubuntu26-utm.yml --tags hosts_file
```

Inventoryの各ホストでは、ホスト名をYAMLのhost key、VM名を `utm_vm_name`、IPv4を `ansible_host` に設定します。各ホストの `utm_provision` は `clone` または `existing` です。`all.vars` には `utm_template_name`、`utm_network_connection`、`utm_global_ipv6_prefix`、`utm_ipv4_prefix_length`、`utm_ipv4_gateway`、`utm_ipv4_dns_servers` を指定します。IPv4は一意にし、DHCP範囲から除外するかルーターで予約してください。既定の `192.168.10.30`〜`.32` は例です。利用前にアドレスの空きとDHCP割り当て範囲を確認してください。

## 新しいMac/UTM環境で必要なテンプレート準備

UTM上にUbuntu 26.04 ServerのVMを作成し、Inventoryの `utm_template_name` と同じ名前（既定値 `ubuntu26-template`）にします。テンプレートはVM作成前に準備し、停止してください。Playbookはテンプレートを起動せず、存在と停止状態だけを確認します。

### 1. QEMU Guest AgentとSSHのインストール

テンプレートVMのコンソールでrootとして実行します。

```sh
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent openssh-server
systemctl enable --now qemu-guest-agent
systemctl enable --now ssh
```

UTMの設定で **Sharing → Enable Clipboard Sharing** を有効にし、QEMU Guest AgentがゲストIPアドレスを報告できるようにします。

### 2. IPv4 DHCPを無効化し、IPv6 SLAACを有効化

このPlaybookはUbuntu ServerのNetplan (`systemd-networkd`) を使用します。インターフェース名がInventoryの `utm_network_connection` と一致することを確認してください。既定値は `enp0s1` です。Cloud-initがネットワーク設定を再生成しないようにし、テンプレートVMのコンソールで設定します。

```sh
mkdir -p /etc/cloud/cloud.cfg.d /etc/netplan
printf 'network: {config: disabled}\n' > /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
```

`/etc/netplan/50-cloud-init.yaml` が存在する場合は、内容を確認し、テンプレート用の設定と重複しないようにしてください。その後、以下のNetplan設定を作成します（インターフェース名は環境に合わせて変更）。

```sh
cat > /etc/netplan/01-utm.yaml <<'EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    enp0s1:
      dhcp4: false
      dhcp6: true
      accept-ra: true
EOF
chmod 600 /etc/netplan/01-utm.yaml
netplan generate
netplan apply
```

`dhcp4: false` でIPv4 DHCPを止め、`accept-ra: true` でルーター広告によるIPv6 SLAACを有効にします。テンプレートにグローバルIPv6アドレスが付き、Macから到達できることを確認します。クローン後はPlaybookが `/etc/netplan/99-ansible-utm.yaml` を作成し、Inventoryの静的IPv4・ゲートウェイ・DNSと、クローン後のNICのMACアドレスを設定します。UTMがクローン時にMACを再生成しても、テンプレートに残った旧MACアドレスがNIC設定に一致しない問題を避けます。

### 3. `toshiyuki` ユーザーのSSH公開鍵認証とパスワードなしsudo

Macに鍵がなければ作成します。

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
```

Playbookはrootではなく `toshiyuki` ユーザーでSSH接続し、root権限が必要なゲスト設定に `sudo -n` を使います。テンプレートには `toshiyuki` ユーザーを用意し、パスワードなしsudoを許可してください。テンプレートVMのコンソールでrootとして次を実行します。

```sh
id toshiyuki
printf 'toshiyuki ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/90-toshiyuki-nopasswd
chmod 440 /etc/sudoers.d/90-toshiyuki-nopasswd
visudo -cf /etc/sudoers.d/90-toshiyuki-nopasswd
```

公開鍵はMacからテンプレートのグローバルIPv6アドレスへ登録します。

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub toshiyuki@<template-ipv6>
```

接続とパスワードなしsudoを確認します。

```sh
ssh -6 -i ~/.ssh/id_ed25519 toshiyuki@<template-ipv6> 'sudo -n true'
```

SSHサービスは有効化した `ssh` を使用します。root SSHログインを許可する必要はありません。

### 4. クローン時のMACアドレス自動生成

テンプレートVMを停止し、UTMでVMの編集画面を開いてネットワーク設定の **Regenerate MAC addresses on clone** を有効にして保存します。UTMのバージョンによって項目の表示位置が異なる場合があります。新しく作ったクローンのMACアドレスがそれぞれ異なることを確認してください。

## `existing` VMをInventoryに含める場合

既存VMは初回接続に使う `utm_ssh_alias` をInventoryに指定してください。対象Ubuntu VMで `toshiyuki` ユーザーの鍵認証とパスワードなしsudoが有効で、指定したSSH接続先が解決・到達可能である必要があります。Playbookは `toshiyuki` としてSSH接続し、`sudo -n` でQEMU Guest Agentをaptからインストールし、UTM経由で取得したIPv6アドレスを使ってホスト名とNetplan設定を適用します。
