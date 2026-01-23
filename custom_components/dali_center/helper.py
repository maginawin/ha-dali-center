"""Helper functions for Dali Center."""

from __future__ import annotations

from typing import Any

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import CONF_GATEWAY_LEGACY, CONF_SERIAL_NUMBER


def migrate_gateway_config(old_data: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy gateway configuration to new format."""
    if CONF_GATEWAY_LEGACY not in old_data:
        return old_data

    gateway_dict = old_data[CONF_GATEWAY_LEGACY]
    return {
        CONF_SERIAL_NUMBER: gateway_dict["gw_sn"],
        CONF_HOST: gateway_dict["gw_ip"],
        CONF_PORT: gateway_dict["port"],
        CONF_NAME: gateway_dict["name"],
        CONF_USERNAME: gateway_dict["username"],
        CONF_PASSWORD: gateway_dict["passwd"],
    }
