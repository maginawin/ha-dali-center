"""Constants for the Dali Center integration."""

from __future__ import annotations

from typing import Final

DOMAIN = "dali_center"
MANUFACTURER = "Sunricher"

CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_GATEWAY_LEGACY = "gateway"

# Dispatcher signal for dynamically adding entities after bus scan.
# Used as f"{SIGNAL_ADD_ENTITIES}_{entry.entry_id}" to isolate per config entry.
SIGNAL_ADD_ENTITIES: Final = f"{DOMAIN}_add_entities"

# Dispatcher signal for bus scan state changes (scanning: bool).
# Used as f"{SIGNAL_SCAN_STATE}_{entry.entry_id}".
SIGNAL_SCAN_STATE: Final = f"{DOMAIN}_scan_state"


def sn_to_mac(serial_number: str) -> str:
    """Convert serial number to MAC address format (6A242121110E -> 6a:24:21:21:11:0e)."""
    sn = serial_number.lower().strip()
    if len(sn) != 12:
        raise ValueError(f"Invalid serial number length: {len(sn)}, expected 12")
    return ":".join(sn[i : i + 2] for i in range(0, 12, 2))
