"""Type definitions for the Dali Center integration."""

from __future__ import annotations

from dataclasses import dataclass

from PySrDaliGateway import DaliGateway, Device, Group, Scene

from homeassistant.config_entries import ConfigEntry


@dataclass
class DaliCenterData:
    """Runtime data for the Dali Center integration."""

    gateway: DaliGateway
    devices: list[Device]
    groups: list[Group]
    scenes: list[Scene]


type DaliCenterConfigEntry = ConfigEntry[DaliCenterData]
