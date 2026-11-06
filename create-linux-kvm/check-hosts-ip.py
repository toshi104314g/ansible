#!/usr/bin/env python3

import ipaddress
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: check-hosts-ip.py IPv4_ADDRESS HOSTNAME", file=sys.stderr)
        return 2

    try:
        address = str(ipaddress.IPv4Address(sys.argv[1]))
    except ipaddress.AddressValueError as error:
        print(f"Invalid IPv4 address: {error}", file=sys.stderr)
        return 2

    hostname = sys.argv[2].rstrip(".").casefold()
    conflicting_lines = []

    try:
        with open("/etc/hosts", encoding="utf-8") as hosts_file:
            for line in hosts_file:
                fields = line.split("#", 1)[0].split()
                if len(fields) < 2 or fields[0] != address:
                    continue

                other_names = [
                    name
                    for name in fields[1:]
                    if name.rstrip(".").casefold() != hostname
                ]
                if other_names:
                    conflicting_lines.append(line.rstrip())
    except OSError as error:
        print(f"Cannot read /etc/hosts: {error}", file=sys.stderr)
        return 2

    if conflicting_lines:
        print("\n".join(conflicting_lines))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
