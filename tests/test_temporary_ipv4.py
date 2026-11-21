import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "create-linux-kvm"
    / "select-temporary-ip.py"
)
SPEC = importlib.util.spec_from_file_location("select_temporary_ip", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TemporaryIPv4SelectionTests(unittest.TestCase):
    ip_probe = MODULE.subprocess.CompletedProcess([], 0, '[{"addr_info":[]}]', "")

    def test_skips_hosts_inventory_and_interface_addresses(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hosts_file = Path(temp_dir) / "hosts"
            hosts_file.write_text("192.168.10.201 router\n", encoding="utf-8")

            with patch.object(
                MODULE.subprocess,
                "run",
                side_effect=[
                    MODULE.subprocess.CompletedProcess(
                        [],
                        0,
                        '[{"addr_info":[{"local":"192.168.10.203"}]}]',
                        "",
                    ),
                    MODULE.subprocess.CompletedProcess([], 0, "", ""),
                ],
            ) as run:
                address = MODULE.select_free_address(
                    "br0",
                    201,
                    204,
                    {MODULE.ipaddress.IPv4Address("192.168.10.202")},
                    hosts_file,
                )

        self.assertEqual(str(address), "192.168.10.204")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0][-1], "192.168.10.204")

    def test_retries_after_arp_detects_an_in_use_address(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hosts_file = Path(temp_dir) / "hosts"
            hosts_file.write_text("", encoding="utf-8")

            with patch.object(
                MODULE.subprocess,
                "run",
                side_effect=[
                    self.ip_probe,
                    MODULE.subprocess.CompletedProcess([], 1, "", ""),
                    MODULE.subprocess.CompletedProcess([], 0, "", ""),
                ],
            ) as run:
                address = MODULE.select_free_address(
                    "br0",
                    201,
                    202,
                    set(),
                    hosts_file,
                )

        self.assertEqual(str(address), "192.168.10.202")
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args_list[1].args[0][-1], "192.168.10.201")
        self.assertEqual(run.call_args_list[2].args[0][-1], "192.168.10.202")

    def test_surfaces_arp_errors_instead_of_assuming_free(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            hosts_file = Path(temp_dir) / "hosts"
            hosts_file.write_text("", encoding="utf-8")

            with patch.object(
                MODULE.subprocess,
                "run",
                side_effect=[
                    self.ip_probe,
                    MODULE.subprocess.CompletedProcess([], 2, "", "permission denied"),
                ],
            ):
                with self.assertRaisesRegex(RuntimeError, "permission denied"):
                    MODULE.select_free_address(
                        "br0",
                        201,
                        201,
                        set(),
                        hosts_file,
                    )


if __name__ == "__main__":
    unittest.main()
