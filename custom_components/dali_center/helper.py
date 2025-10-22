"""Helper functions for Dali Center."""

from typing import Any

from PySrDaliGateway import DaliGateway

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from .const import CONF_GATEWAY_LEGACY, CONF_SERIAL_NUMBER


def gateway_to_dict(gateway: DaliGateway) -> dict[str, Any]:
    """Convert DaliGateway instance to dictionary format."""
    return {
        "gw_sn": gateway.gw_sn,
        "gw_ip": gateway.gw_ip,
        "port": gateway.port,
        "name": gateway.name,
        "username": gateway.username,
        "passwd": gateway.passwd,
        "is_tls": gateway.is_tls,
    }


def migrate_gateway_config(old_data: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy gateway configuration to new format."""
    if CONF_GATEWAY_LEGACY not in old_data:
        return old_data

    gateway_dict = old_data[CONF_GATEWAY_LEGACY]
    return {
        CONF_SERIAL_NUMBER: gateway_dict.get("gw_sn"),
        CONF_HOST: gateway_dict.get("gw_ip"),
        CONF_PORT: gateway_dict.get("port"),
        CONF_NAME: gateway_dict.get("name"),
        CONF_USERNAME: gateway_dict.get("username"),
        CONF_PASSWORD: gateway_dict.get("passwd"),
    }


def find_set_differences(
    list1: list[dict[str, Any]], list2: list[dict[str, Any]], attr_name: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Calculate the difference between two object lists.

    Args:
        list1: First list of objects
        list2: Second list of objects
        attr_name: Name of attribute to compare (e.g. "unique_id")

    Returns:
        Tuple containing:
        - unique1: List of objects that exist in list1 but not in list2
        - unique2: List of objects that exist in list2 but not in list1
    """
    set1_keys = {obj[attr_name] for obj in list1}
    set2_keys = {obj[attr_name] for obj in list2}
    unique1 = [obj for obj in list1 if obj[attr_name] not in set2_keys]
    unique2 = [obj for obj in list2 if obj[attr_name] not in set1_keys]
    return unique1, unique2
