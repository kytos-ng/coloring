"""Utilities."""
import re

MAC_ADDR = re.compile("([0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}$")


def make_unicast_local_mac(mac: str) -> str:
    """
    The first two bits (b0, b1) of the most significant MAC address byte is for
    its uniquiness and wether its locally administered or not. This functions
    ensures it's a unicast (b0 -> 0) and locally administered (b1 -> 1).
    """
    if not re.search(MAC_ADDR, mac):
        msg = "Invalid mac '{mac}': expected this regex format: {MAC_ADDR}"
        raise ValueError(msg)
    mac = mac.lower()
    return mac[:1] + "e" + mac[2:]
