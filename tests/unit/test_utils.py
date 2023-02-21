"""Test utils.py."""
import pytest


from napps.amlight.coloring.utils import make_unicast_local_mac


def test_make_unicast_local_mac_valid() -> None:
    """test make_unicast_local_mac."""
    mac = "31:94:06:ee:ee:ee"
    assert make_unicast_local_mac(mac) == "3e:94:06:ee:ee:ee"


@pytest.mark.parametrize("mac", ["31:94:06:ee:ee:eea", "a", ""])
def test_make_unicast_local_mac_errors(mac) -> None:
    """test make_unicast_local_mac."""
    with pytest.raises(ValueError):
        assert make_unicast_local_mac(mac)
