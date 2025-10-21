"""Type definitions for the Dali Center integration."""

from dataclasses import dataclass
from typing import Any, TypedDict

from PySrDaliGateway import DaliGateway

from homeassistant.config_entries import ConfigEntry


class ConfigData(TypedDict, total=False):
    """Contains configuration data for the integration."""

    serial_number: str
    host: str
    port: int
    name: str
    username: str
    password: str
    devices: list[dict[str, Any]]
    groups: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    gateway: dict[str, Any]


@dataclass
class DaliCenterData:
    """Runtime data for the Dali Center integration."""

    gateway: DaliGateway


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
