#!/usr/bin/env python3

import argparse
import ipaddress
import json
import subprocess
import sys
from pathlib import Path


def hosts_addresses(hosts_file: Path) -> set[ipaddress.IPv4Address]:
    addresses = set()
    try:
        for line in hosts_file.read_text(encoding="utf-8").splitlines():
            fields = line.split("#", 1)[0].split()
            if not fields:
                continue
            try:
                addresses.add(ipaddress.IPv4Address(fields[0]))
            except ipaddress.AddressValueError:
                continue
    except OSError as error:
        raise RuntimeError(f"Cannot read {hosts_file}: {error}") from error
    return addresses


def interface_addresses(interface: str) -> set[ipaddress.IPv4Address]:
    try:
        result = subprocess.run(
            ["ip", "-j", "-4", "address", "show", "dev", interface],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as error:
        raise RuntimeError(f"Cannot inspect addresses on {interface}: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"Cannot inspect addresses on {interface} "
            f"(exit {result.returncode}): {detail}"
        )

    try:
        links = json.loads(result.stdout)
        return {
            ipaddress.IPv4Address(address["local"])
            for link in links
            for address in link.get("addr_info", [])
        }
    except (KeyError, json.JSONDecodeError, ipaddress.AddressValueError) as error:
        raise RuntimeError(f"Cannot parse IPv4 addresses on {interface}: {error}") from error


def select_free_address(
    interface: str,
    start: int,
    end: int,
    excluded: set[ipaddress.IPv4Address],
    hosts_file: Path,
) -> ipaddress.IPv4Address:
    if not 2 <= start <= end <= 254:
        raise ValueError("The temporary address range must be within 192.168.10.2-254.")

    unavailable = excluded | hosts_addresses(hosts_file) | interface_addresses(interface)
    for last_octet in range(start, end + 1):
        candidate = ipaddress.IPv4Address(f"192.168.10.{last_octet}")
        if candidate in unavailable:
            continue

        try:
            result = subprocess.run(
                [
                    "arping",
                    "-D",
                    "-q",
                    "-I",
                    interface,
                    "-c",
                    "2",
                    "-w",
                    "2",
                    str(candidate),
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        except OSError as error:
            raise RuntimeError(f"Cannot run arping: {error}") from error

        if result.returncode == 0:
            return candidate
        if result.returncode != 1:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"arping failed for {candidate} on {interface} "
                f"(exit {result.returncode}): {detail}"
            )

    raise RuntimeError(
        f"No unused address found in 192.168.10.{start}-192.168.10.{end}."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", required=True)
    parser.add_argument("--start", required=True, type=int)
    parser.add_argument("--end", required=True, type=int)
    parser.add_argument("--exclude", default="")
    parser.add_argument("--hosts-file", default="/etc/hosts", type=Path)
    args = parser.parse_args()

    try:
        excluded = {
            ipaddress.IPv4Address(value)
            for value in args.exclude.split(",")
            if value
        }
        address = select_free_address(
            args.interface,
            args.start,
            args.end,
            excluded,
            args.hosts_file,
        )
    except (ipaddress.AddressValueError, RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    print(address)
    return 0


if __name__ == "__main__":
    sys.exit(main())
