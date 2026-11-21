#!/usr/bin/env python3
"""Configure the bridged UTM network interfaces for an inventory guest."""

import argparse
import copy
import json
import os
import plistlib
import secrets
import stat
import subprocess
import tempfile
from pathlib import Path


def new_mac_address():
    address = bytearray(secrets.token_bytes(6))
    address[0] = (address[0] | 0x02) & 0xFE
    return ":".join(f"{octet:02X}" for octet in address)


def applescript_string(value):
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("UTM configuration values cannot contain control characters")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def network_for_bridge(template, bridge, used_mac_addresses):
    network = copy.deepcopy(template)
    network.pop("HostNetUuid", None)
    network.pop("SharedNetwork", None)
    network["BridgeInterface"] = bridge
    network["Hardware"] = network.get("Hardware", "virtio-net-pci")
    network["IsolateFromHost"] = False
    network["Mode"] = "Bridged"
    network["PortForward"] = []

    mac_address = network.get("MacAddress", "").upper()
    if not mac_address or mac_address in used_mac_addresses:
        mac_address = new_mac_address()
    network["MacAddress"] = mac_address
    used_mac_addresses.add(mac_address)
    return network


def utm_networks(vm_name):
    script = (
        'var app = Application("UTM"); '
        f"var vm = app.virtualMachines.byName({json.dumps(vm_name)}); "
        "JSON.stringify(vm.configuration().networkInterfaces.map(network => ({"
        "hardware:network.hardware, "
        "mode:network.mode, "
        "address:network.address, "
        "hostInterface:network.hostInterface"
        "})))"
    )
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise RuntimeError(
            f"Could not read UTM's cached network configuration for {vm_name}: {detail}"
        ) from error

    try:
        networks = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"UTM returned an invalid network configuration for {vm_name}: {result.stdout.strip()}"
        ) from error
    if not isinstance(networks, list) or any(not isinstance(network, dict) for network in networks):
        raise RuntimeError(
            f"UTM returned an invalid network configuration for {vm_name}: {networks!r}"
        )
    return networks


def expected_utm_networks(networks):
    return [
        {
            "hardware": network["Hardware"],
            "mode": "bridged",
            "address": network["MacAddress"],
            "hostInterface": network["BridgeInterface"],
        }
        for network in networks
    ]


def bridged_interfaces(management_host_interface, lab_host_interface=None, dmz_host_interface=None):
    interfaces = [management_host_interface]
    if lab_host_interface:
        interfaces.append(lab_host_interface)
    if dmz_host_interface:
        interfaces.append(dmz_host_interface)
    return interfaces


def update_utm_configuration(vm_name, networks, existing_network_count):
    network_records = []
    for index, network in enumerate(networks):
        fields = []
        if index < existing_network_count:
            fields.append(f"index:{index}")
        # UTM creates an additional interface when the index is omitted.
        fields.extend(
            [
                f"hardware:{applescript_string(network['Hardware'])}",
                "mode:bridged",
                f"address:{applescript_string(network['MacAddress'])}",
                f"host interface:{applescript_string(network['BridgeInterface'])}",
                "port forwards:{}",
            ]
        )
        network_records.append("{" + ", ".join(fields) + "}")

    vm_name_literal = applescript_string(vm_name)
    script = (
        'tell application "UTM"\n'
        "  set networkOverride to {network interfaces:{"
        + ", ".join(network_records)
        + "}}\n"
        f"  set fullConfiguration to networkOverride & "
        f"(configuration of virtual machine {vm_name_literal})\n"
        f"  update configuration of virtual machine {vm_name_literal} "
        "with fullConfiguration\n"
        "end tell"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or error.stdout.strip() or str(error)
        raise RuntimeError(
            f"Could not update UTM's cached configuration for {vm_name}: {detail}"
        ) from error


def copy_extended_attributes(source, destination):
    attributes = subprocess.run(
        ["xattr", str(source)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    for attribute in attributes:
        value = subprocess.run(
            ["xattr", "-px", attribute, str(source)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["xattr", "-wx", attribute, value, str(destination)],
            check=True,
            capture_output=True,
            text=True,
        )


def configure_networks(documents_directory, vm_name, bridges, running):
    if not vm_name or vm_name in {".", ".."} or "/" in vm_name or "\\" in vm_name:
        raise ValueError(f"Invalid UTM VM name: {vm_name!r}")

    documents_directory = Path(documents_directory).resolve()
    config_path = (documents_directory / f"{vm_name}.utm" / "config.plist").resolve()
    try:
        config_path.relative_to(documents_directory)
    except ValueError as error:
        raise ValueError(f"UTM configuration path is outside the documents directory: {config_path}") from error
    if not config_path.is_file():
        raise ValueError(f"UTM configuration file not found: {config_path}")

    original_stat = config_path.stat()
    original_mode = stat.S_IMODE(original_stat.st_mode)
    with config_path.open("rb") as config_file:
        config = plistlib.load(config_file)

    original_networks = config.get("Network")
    if not isinstance(original_networks, list) or not original_networks:
        raise ValueError(f"UTM configuration has no Network entries: {config_path}")
    if any(not isinstance(network, dict) for network in original_networks):
        raise ValueError(f"UTM configuration has an invalid Network entry: {config_path}")

    used_mac_addresses = set()
    networks = []
    for index, bridge in enumerate(bridges):
        template = original_networks[index] if index < len(original_networks) else original_networks[0]
        networks.append(network_for_bridge(template, bridge, used_mac_addresses))

    configuration_changed = networks != original_networks
    cached_networks = utm_networks(vm_name)
    cache_changed = cached_networks != expected_utm_networks(networks)
    if running and (configuration_changed or cache_changed):
        raise ValueError(
            f"UTM VM is running and its network configuration needs changes: {config_path}"
        )

    if running:
        return False

    if configuration_changed:
        config["Network"] = networks
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=config_path.parent, prefix=".config.plist.", delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                os.fchmod(temporary_file.fileno(), original_mode)
                if (
                    os.fstat(temporary_file.fileno()).st_uid != original_stat.st_uid
                    or os.fstat(temporary_file.fileno()).st_gid != original_stat.st_gid
                ):
                    os.fchown(
                        temporary_file.fileno(),
                        original_stat.st_uid,
                        original_stat.st_gid,
                    )
                copy_extended_attributes(config_path, temporary_file.name)
                plistlib.dump(config, temporary_file, fmt=plistlib.FMT_XML, sort_keys=False)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, config_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    if cache_changed:
        update_utm_configuration(vm_name, networks, len(cached_networks))
    return configuration_changed or cache_changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents_directory", type=Path)
    parser.add_argument("vm_name")
    parser.add_argument("--lab", action="store_true", help="inventory has lab_ipv4_address")
    parser.add_argument("--dmz", action="store_true", help="inventory has dmz_ipv4_address")
    parser.add_argument("--management-host-interface", required=True)
    parser.add_argument("--lab-host-interface")
    parser.add_argument("--dmz-host-interface")
    parser.add_argument("--running", action="store_true", help="refuse changes to a running VM")
    args = parser.parse_args()

    if args.lab != bool(args.lab_host_interface):
        parser.error("--lab and --lab-host-interface must be provided together")
    if args.dmz != bool(args.dmz_host_interface):
        parser.error("--dmz and --dmz-host-interface must be provided together")
    if not args.management_host_interface:
        parser.error("--management-host-interface must not be empty")

    bridges = bridged_interfaces(
        args.management_host_interface,
        args.lab_host_interface,
        args.dmz_host_interface,
    )

    try:
        changed = configure_networks(
            args.documents_directory,
            args.vm_name,
            bridges,
            args.running,
        )
    except (
        OSError,
        plistlib.InvalidFileException,
        subprocess.CalledProcessError,
        RuntimeError,
        ValueError,
    ) as error:
        parser.error(str(error))
    print("changed" if changed else "unchanged")


if __name__ == "__main__":
    main()
