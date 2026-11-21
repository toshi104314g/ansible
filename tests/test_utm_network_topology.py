import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "create-linux-utm"
    / "configure-network-bridges.py"
)
SPEC = importlib.util.spec_from_file_location("configure_network_bridges", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class UTMNetworkTopologyTests(unittest.TestCase):
    def test_selects_only_requested_host_interfaces_in_guest_order(self):
        self.assertEqual(
            MODULE.bridged_interfaces("en7"),
            ["en7"],
        )
        self.assertEqual(
            MODULE.bridged_interfaces("en7", lab_host_interface="vlan0"),
            ["en7", "vlan0"],
        )
        self.assertEqual(
            MODULE.bridged_interfaces("en7", dmz_host_interface="vlan1"),
            ["en7", "vlan1"],
        )
        self.assertEqual(
            MODULE.bridged_interfaces(
                "en7",
                lab_host_interface="vlan0",
                dmz_host_interface="vlan1",
            ),
            ["en7", "vlan0", "vlan1"],
        )


if __name__ == "__main__":
    unittest.main()
