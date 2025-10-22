"""Type definitions for the Dali Center integration."""

from dataclasses import dataclass

from PySrDaliGateway import DaliGateway, Device, Group, Scene

from homeassistant.config_entries import ConfigEntry


@dataclass
class DaliCenterData:
    """Runtime data for the Dali Center integration.

    Contains the gateway connection and all discovered entities.
    Entities are discovered during setup, not stored in config entry.
    """

    gateway: DaliGateway
    devices: list[Device]
    groups: list[Group]
    scenes: list[Scene]


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
