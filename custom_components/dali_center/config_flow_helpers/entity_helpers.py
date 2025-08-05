"""Entity discovery and selection helpers for config flow."""

import logging
from typing import Any, Optional
import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from PySrDaliGateway import DaliGateway, DeviceType, GroupType, SceneType
from PySrDaliGateway.exceptions import DaliGatewayError
from ..types import ConfigData

_LOGGER = logging.getLogger(__name__)


class EntityDiscoveryHelper:
    """Helper class for entity discovery and selection logic."""

    @staticmethod
    async def discover_entities(
        gateway: DaliGateway,
        discover_devices: bool = True,
        discover_groups: bool = True,
        discover_scenes: bool = True
    ) -> dict[str, list[DeviceType] | list[GroupType] | list[SceneType]]:
        """Discover entities from gateway."""
        discovered: dict[
            str, list[DeviceType] | list[GroupType] | list[SceneType]
        ] = {}

        if discover_devices:
            try:
                discovered["devices"] = await gateway.discover_devices()
                _LOGGER.info(
                    "Found %d devices on gateway %s",
                    len(discovered["devices"]),
                    gateway.gw_sn
                )
            except DaliGatewayError as e:
                _LOGGER.warning(
                    "Error discovering devices on gateway %s: %s",
                    gateway.gw_sn, e
                )
                discovered["devices"] = []
            except Exception as e:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Unexpected error discovering devices on gateway %s: %s",
                    gateway.gw_sn, e
                )
                discovered["devices"] = []

        if discover_groups:
            try:
                discovered["groups"] = await gateway.discover_groups()
                _LOGGER.info(
                    "Found %d groups on gateway %s",
                    len(discovered["groups"]),
                    gateway.gw_sn
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Unexpected error discovering groups on gateway %s: %s",
                    gateway.gw_sn, e
                )
                discovered["groups"] = []

        if discover_scenes:
            try:
                discovered["scenes"] = await gateway.discover_scenes()
                _LOGGER.info(
                    "Found %d scenes on gateway %s",
                    len(discovered["scenes"]),
                    gateway.gw_sn
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Unexpected error discovering scenes on gateway %s: %s",
                    gateway.gw_sn, e
                )
                discovered["scenes"] = []

        return discovered

    @staticmethod
    def prepare_entity_selection_schema(
        devices: list,
        groups: list,
        scenes: list,
        existing_selections: Optional[dict[str, list]] = None,
        show_diff: bool = False
    ) -> vol.Schema:
        """Prepare entity selection schema."""
        schema_dict = {}

        # Prepare device selection options
        if devices:
            device_options = {}
            existing_device_ids = {
                d["unique_id"] for d in existing_selections.get("devices", [])
            } if existing_selections else set()

            for device in devices:
                label = f"{device["name"]}"
                if show_diff and existing_selections and \
                        device["unique_id"] not in existing_device_ids:
                    label = f"[NEW] {label}"
                device_options[device["unique_id"]] = label

            # Add removed devices if showing diff
            if show_diff and existing_selections and \
                    "devices" in existing_selections:
                current_device_ids = {d["unique_id"] for d in devices}
                for device in existing_selections["devices"]:
                    if device["unique_id"] not in current_device_ids:
                        device_options[device["unique_id"]] = \
                            f"[REMOVED] {device["name"]}"

            # Default selection
            if existing_selections is None:
                # Select all for initial setup
                default_devices = list(device_options.keys())
            else:
                # Keep existing selections that are still available
                default_devices = [
                    unique_id for unique_id in existing_device_ids
                    if unique_id in device_options
                ]

            schema_dict[vol.Optional("devices", default=default_devices)] = \
                cv.multi_select(device_options)

        # Prepare group selection options
        if groups:
            group_options = {}
            existing_ids = {
                g["unique_id"] for g in existing_selections.get("groups", [])
            } if existing_selections else set()

            for group in groups:
                label = f"{group["name"]} (Channel {
                    group["channel"]}, Group {group["id"]})"
                if show_diff and existing_selections and \
                        group["unique_id"] not in existing_ids:
                    label = f"[NEW] {label}"
                group_options[group["unique_id"]] = label

            # Add removed groups if showing diff
            if show_diff and existing_selections and \
                    "groups" in existing_selections:
                current_ids = {g["unique_id"] for g in groups}
                for group in existing_selections["groups"]:
                    if group["unique_id"] not in current_ids:
                        group_options[group["unique_id"]] = \
                            f"[REMOVED] {group["name"]}"

            # Default selection
            if existing_selections is None:
                # Select all for initial setup
                default_groups = list(group_options.keys())
            else:
                # Keep existing selections
                default_groups = [
                    unique_id for unique_id in existing_ids
                    if unique_id in group_options
                ]

            schema_dict[vol.Optional("groups", default=default_groups)] = \
                cv.multi_select(group_options)

        # Prepare scene selection options
        if scenes:
            scene_options = {}
            existing_ids = {
                s["unique_id"] for s in existing_selections.get("scenes", [])
            } if existing_selections else set()

            for scene in scenes:
                label = f"{scene["name"]} (Channel {
                    scene["channel"]}, Scene {scene["id"]})"
                if show_diff and existing_selections and \
                        scene["unique_id"] not in existing_ids:
                    label = f"[NEW] {label}"
                scene_options[scene["unique_id"]] = label

            # Add removed scenes if showing diff
            if show_diff and existing_selections and \
                    "scenes" in existing_selections:
                current_ids = {s["unique_id"] for s in scenes}
                for scene in existing_selections["scenes"]:
                    if scene["unique_id"] not in current_ids:
                        scene_options[scene["unique_id"]] = \
                            f"[REMOVED] {scene["name"]}"

            if existing_selections is None:
                # Select all for initial setup
                default_scenes = list(scene_options.keys())
            else:
                # Keep existing selections
                default_scenes = [
                    unique_id for unique_id in existing_ids
                    if unique_id in scene_options
                ]

            schema_dict[vol.Optional("scenes", default=default_scenes)] = \
                cv.multi_select(scene_options)

        return vol.Schema(schema_dict)

    @staticmethod
    def filter_selected_entities(
        user_input: dict[str, Any],
        discovered_entities: dict[str, list]
    ) -> ConfigData:
        """Filter selected entities from user input."""
        selected: ConfigData = {}

        # Filter devices
        if "devices" in user_input and "devices" in discovered_entities:
            selected_ids = user_input["devices"]
            selected["devices"] = [
                device for device in discovered_entities["devices"]
                if device["unique_id"] in selected_ids
            ]

        # Filter groups
        if "groups" in user_input and "groups" in discovered_entities:
            selected_ids = user_input["groups"]
            selected["groups"] = [
                group for group in discovered_entities["groups"]
                if group["unique_id"] in selected_ids
            ]

        # Filter scenes
        if "scenes" in user_input and "scenes" in discovered_entities:
            selected_ids = user_input["scenes"]
            selected["scenes"] = [
                scene for scene in discovered_entities["scenes"]
                if scene["unique_id"] in selected_ids
            ]

        return selected
