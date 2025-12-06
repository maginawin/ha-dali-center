"""Constants for the Dali Center integration."""

from typing import Final

DOMAIN = "dali_center"
MANUFACTURER = "Sunricher"

CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_GATEWAY_LEGACY = "gateway"


def sn_to_mac(serial_number: str) -> str:
    """Convert serial number to MAC address format (6A242121110E -> 6a:24:21:21:11:0e)."""
    sn = serial_number.lower().strip()
    if len(sn) != 12:
        raise ValueError(f"Invalid serial number length: {len(sn)}, expected 12")
    return ":".join(sn[i : i + 2] for i in range(0, 12, 2))
