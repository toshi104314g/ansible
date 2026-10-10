# Rocky Linux 9 VM management on UTM

このPlaybookは、Inventoryを設定元としてUTM上のRocky Linux 9 VMを作成・設定・削除します。実行入口は `create-rocky9-utm.yml` です。

## このPlaybookでできること

- UTMのテンプレートVMをクローンしてInventoryに記載したVMを作成します。
- ゲストのホスト名と静的IPv4アドレスをInventoryの値に合わせて設定します。IPv6 SLAACは維持します。
- `existing` として指定した既存VMも、VMを作り直さずにホスト名とIPv4アドレスを設定できます。
- Inventory内のVMをUTMから削除し、Macの `/etc/hosts` にある管理対象エントリを削除します。
- 作成時はMacの `/etc/hosts` をInventoryのホスト名とIPv4アドレスに合わせて更新します。

VMの設定元は `-i` で選択したInventoryファイルです。ホストの追加・変更・削除はそのInventoryを編集してください。各VMの `utm_provision` は、テンプレートから作成する場合は `clone`、既存VMを設定する場合は `existing` にします。事故防止のため、Inventoryファイルを明示しない実行や複数Inventoryの指定は受け付けません。

## Playbookの起動方法

リポジトリのルートディレクトリで実行します。タグを省略した場合は `create` が既定の動作です。

```sh
# Inventoryに記載されたVMを作成・設定する（既定の動作）
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_samba-ad.yml --ask-become-pass create-rocky9-utm/create-rocky9-utm.yml

# createを明示して作成・設定する
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_samba-ad.yml --ask-become-pass create-rocky9-utm/create-rocky9-utm.yml --tags create

# Inventoryに記載されたVMを削除する
PATH="/opt/homebrew/bin:$PATH" ansible-playbook -i inventory/inventory_samba-ad.yml --ask-become-pass create-rocky9-utm/create-rocky9-utm.yml --tags delete
```

テスト用など別のInventoryを使う場合は、`-i` のパスを差し替えてください。指定したInventoryだけが作成・削除対象になり、`vars.yml` に既定Inventoryのファイル名はありません。

`--ask-become-pass` は、Macの `/etc/hosts` を更新・削除する際のsudoパスワードを入力するための指定です。`/etc/hosts` は選択したInventoryに記載されたホスト名ごとに更新・削除し、他のInventoryに由来するホストエントリは保持します。IPアドレスを変更した場合は同じホスト名の既存行をInventoryの `ansible_host` に置き換えます。

削除はUTM VMを完全に削除する操作です。対象は実行前にInventoryで確認してください。Playbookは確認入力として `DELETE` を要求します。テンプレートVMは削除対象から保護されます。

作成Playbookは既に存在するクローンを再利用し、ホスト名とネットワーク設定をInventoryに合わせます。Inventoryからホストを削除しても、そのVMは自動削除されません。VMの削除後にInventoryからエントリを除いてください。

## 新しいホスト環境での事前準備

以下は、新しいMac/UTM環境でテンプレートVMを用意するときの手順です。UTMとAnsibleをインストールし、UTMでRocky Linux 9のVMを新規作成してください。テンプレート名はInventoryの `all.vars.utm_template_name` と一致させます（既定値は `rocky9-template`）。テンプレートには保存しておきたいデータを置かず、ドメイン参加もさせないでください。

### 1. テンプレートVMにQEMU Guest AgentとSSHをインストール

テンプレートVMのコンソールでrootとして実行します。

```sh
dnf install -y qemu-guest-agent openssh-server
systemctl enable --now qemu-guest-agent
systemctl enable --now sshd
```

UTMのゲストIPアドレス取得を使うため、VMの設定でクリップボード共有を有効にしてください（**Sharing → Enable Clipboard Sharing**）。

### 2. IPv4 DHCPを無効化し、IPv6自動設定を有効化

テンプレートVMのNetworkManager接続プロファイル名を確認します。

```sh
nmcli connection show
```

既定Inventoryの `utm_network_connection` は `enp0s1` です。Inventoryの値と一致する接続プロファイル名を使い、テンプレートVMのコンソールで実行してください。

```sh
nmcli connection modify enp0s1 ipv4.method disabled ipv6.method auto
nmcli connection up enp0s1
```

`ipv6.method auto` はルーター広告（RA）によるIPv6自動設定を有効にし、SLAACを利用できる状態にします。IPv4は無効となり、クローン後にPlaybookがInventoryの静的IPv4アドレスを設定します。テンプレートVMにグローバルIPv6アドレスが割り当てられ、MacからそのIPv6アドレスへ接続できることを確認してください。

### 3. MacからrootへSSH鍵で接続できるようにする

Playbookは既定でMacの `~/.ssh/id_ed25519` を使います。公開鍵がまだない場合はMacで作成します。

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
```

初期設定時に一時的なrootパスワード認証でSSH接続できる場合は、Macから公開鍵を登録します。`<template-ipv6>` はテンプレートVMのグローバルIPv6アドレスに置き換えてください。

```sh
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<template-ipv6>
```

`ssh-copy-id` が使えない場合は、テンプレートVMのコンソールで `/root/.ssh/authorized_keys` にMacの `~/.ssh/id_ed25519.pub` の内容を登録し、権限を設定してください。

```sh
mkdir -p /root/.ssh
chmod 700 /root/.ssh
# 公開鍵の内容を1行でauthorized_keysに追加してから実行
chmod 600 /root/.ssh/authorized_keys
```

Macから鍵認証で接続できることを確認します。

```sh
ssh -6 -i ~/.ssh/id_ed25519 root@<template-ipv6>
```

### 4. クローン時のMACアドレス自動生成を有効化

テンプレートVMを停止し、UTMでそのVMの編集画面を開きます。ネットワーク設定にある **Regenerate MAC addresses on clone**（クローン時にMACアドレスを再生成）のチェックを有効にして保存してください。UTMのバージョンによって設定項目の表示位置が異なる場合があります。複製した各VMのMACアドレスが異なることを確認してください。この設定が無効だと、クローン間でMACアドレスが重複するおそれがあります。

テンプレートVMは事前準備を済ませ、停止した状態にしてください。Playbookはテンプレートの存在と停止状態を確認しますが、起動・停止やネットワーク設定の変更は行いません。稼働中の場合はエラーで停止するため、UTMで停止してから再実行してください。

## Inventoryとネットワークについて

選択したInventoryファイルでVM名、ホスト名、IPv4アドレス、テンプレート名、ネットワーク接続名などを管理します。各ホストのIPv4アドレスは `ansible_host` に指定し、Playbookはこの値をSSH接続先・ゲストの静的IPv4アドレス・Macの `/etc/hosts` 更新に共通して使用します。IPv4アドレスは一意にし、ルーターで予約するかDHCP配布範囲から除外してください。

クローンではなく既存VMを設定する場合は、`utm_provision: existing` と、初回接続に使う `utm_ssh_alias` をInventoryに指定します。そのVMには事前にroot鍵認証で接続できる必要があります。
