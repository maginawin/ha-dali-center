"""Entity discovery and selection helpers for config flow."""

import logging
from typing import Any, cast

from PySrDaliGateway import DaliGateway, DeviceType, GroupType, SceneType
from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from ..types import ConfigData

_LOGGER = logging.getLogger(__name__)


class EntityDiscoveryHelper:
    """Helper class for entity discovery and selection logic."""

    @staticmethod
    async def discover_entities(
        gateway: DaliGateway,
        discover_devices: bool = True,
        discover_groups: bool = True,
        discover_scenes: bool = True,
    ) -> dict[str, Any]:
        """Discover entities from gateway."""
        discovered: dict[str, Any] = {}

        if discover_devices:
            try:
                discovered["devices"] = await gateway.discover_devices()
                _LOGGER.info(
                    "Found %d devices on gateway %s",
                    len(discovered["devices"]),
                    gateway.gw_sn,
                )
            except DaliGatewayError as e:
                _LOGGER.warning(
                    "Error discovering devices on gateway %s: %s", gateway.gw_sn, e
                )
                discovered["devices"] = []
            except Exception as e:
                _LOGGER.warning(
                    "Unexpected error discovering devices on gateway %s: %s",
                    gateway.gw_sn,
                    e,
                )
                discovered["devices"] = []

        if discover_groups:
            try:
                discovered["groups"] = await gateway.discover_groups()
                _LOGGER.info(
                    "Found %d groups on gateway %s",
                    len(discovered["groups"]),
                    gateway.gw_sn,
                )
            except Exception as e:
                _LOGGER.warning(
                    "Unexpected error discovering groups on gateway %s: %s",
                    gateway.gw_sn,
                    e,
                )
                discovered["groups"] = []

        if discover_scenes:
            try:
                discovered["scenes"] = await gateway.discover_scenes()
                _LOGGER.info(
                    "Found %d scenes on gateway %s",
                    len(discovered["scenes"]),
                    gateway.gw_sn,
                )
            except Exception as e:
                _LOGGER.warning(
                    "Unexpected error discovering scenes on gateway %s: %s",
                    gateway.gw_sn,
                    e,
                )
                discovered["scenes"] = []

        return discovered

    @staticmethod
    def prepare_entity_selection_schema(
        devices: list[DeviceType],
        groups: list[GroupType],
        scenes: list[SceneType],
        existing_selections: dict[str, Any] | None = None,
        show_diff: bool = False,
    ) -> vol.Schema:
        """Prepare entity selection schema."""
        schema_dict = {}

        # Prepare device selection options
        if devices:
            device_options: dict[str, str] = {}
            existing_device_ids: set[str] = set()
            if existing_selections:
                existing_devices: list[dict[str, Any]] = existing_selections.get(
                    "devices", []
                )
                existing_device_ids = {
                    str(d.get("unique_id", ""))
                    for d in existing_devices
                    if "unique_id" in d
                }

            for device in devices:
                device_dict = cast("dict[str, Any]", device)
                unique_id = str(device_dict.get("unique_id", ""))
                name = str(device_dict.get("name", ""))
                label = f"{name}"
                if (
                    show_diff
                    and existing_selections
                    and unique_id not in existing_device_ids
                ):
                    label = f"[NEW] {label}"
                device_options[unique_id] = label

            # Add removed devices if showing diff
            if show_diff and existing_selections and "devices" in existing_selections:
                current_device_ids = {
                    str(cast("dict[str, Any]", d).get("unique_id", "")) for d in devices
                }
                for device in existing_selections["devices"]:
                    device_dict = cast("dict[str, Any]", device)
                    device_unique_id = str(device_dict.get("unique_id", ""))
                    device_name = str(device_dict.get("name", ""))
                    if device_unique_id not in current_device_ids:
                        device_options[device_unique_id] = f"[REMOVED] {device_name}"

            # Default selection
            default_devices: list[str] = []
            if existing_selections is None:
                # Select all for initial setup
                default_devices = list(device_options.keys())
            else:
                # Keep existing selections that are still available
                default_devices = [
                    unique_id
                    for unique_id in existing_device_ids
                    if unique_id in device_options
                ]

            schema_dict[vol.Optional("devices", default=default_devices)] = (
                cv.multi_select(device_options)
            )

        # Prepare group selection options
        if groups:
            group_options: dict[str, str] = {}
            existing_ids: set[str] = set()
            if existing_selections:
                existing_groups = cast(
                    "list[dict[str, Any]]", existing_selections.get("groups", [])
                )
                existing_ids = {
                    str(g.get("unique_id", ""))
                    for g in existing_groups
                    if "unique_id" in g
                }

            for group in groups:
                group_dict = cast("dict[str, Any]", group)
                unique_id = str(group_dict.get("unique_id", ""))
                name = str(group_dict.get("name", ""))
                channel = str(group_dict.get("channel", ""))
                group_id = str(group_dict.get("id", ""))
                label = f"{name} (Channel {channel}, Group {group_id})"
                if show_diff and existing_selections and unique_id not in existing_ids:
                    label = f"[NEW] {label}"
                group_options[unique_id] = label

            # Add removed groups if showing diff
            if show_diff and existing_selections and "groups" in existing_selections:
                current_ids = {
                    str(cast("dict[str, Any]", g).get("unique_id", "")) for g in groups
                }
                for group in existing_selections["groups"]:
                    group_dict = cast("dict[str, Any]", group)
                    group_unique_id = str(group_dict.get("unique_id", ""))
                    group_name = str(group_dict.get("name", ""))
                    if group_unique_id not in current_ids:
                        group_options[group_unique_id] = f"[REMOVED] {group_name}"

            # Default selection
            default_groups: list[str] = []
            if existing_selections is None:
                # Select all for initial setup
                default_groups = list(group_options.keys())
            else:
                # Keep existing selections
                default_groups = [
                    unique_id
                    for unique_id in existing_ids
                    if unique_id in group_options
                ]

            schema_dict[vol.Optional("groups", default=default_groups)] = (
                cv.multi_select(group_options)
            )

        # Prepare scene selection options
        if scenes:
            scene_options: dict[str, str] = {}
            existing_scene_ids: set[str] = set()
            if existing_selections:
                existing_scenes = cast(
                    "list[dict[str, Any]]", existing_selections.get("scenes", [])
                )
                existing_scene_ids = {
                    str(s.get("unique_id", ""))
                    for s in existing_scenes
                    if "unique_id" in s
                }

            for scene in scenes:
                scene_dict = cast("dict[str, Any]", scene)
                unique_id = str(scene_dict.get("unique_id", ""))
                name = str(scene_dict.get("name", ""))
                channel = str(scene_dict.get("channel", ""))
                scene_id = str(scene_dict.get("id", ""))
                label = f"{name} (Channel {channel}, Scene {scene_id})"
                if (
                    show_diff
                    and existing_selections
                    and unique_id not in existing_scene_ids
                ):
                    label = f"[NEW] {label}"
                scene_options[unique_id] = label

            # Add removed scenes if showing diff
            if show_diff and existing_selections and "scenes" in existing_selections:
                current_ids = {
                    str(cast("dict[str, Any]", s).get("unique_id", "")) for s in scenes
                }
                for scene in existing_selections["scenes"]:
                    scene_dict = cast("dict[str, Any]", scene)
                    scene_unique_id = str(scene_dict.get("unique_id", ""))
                    scene_name = str(scene_dict.get("name", ""))
                    if scene_unique_id not in current_ids:
                        scene_options[scene_unique_id] = f"[REMOVED] {scene_name}"

            # Default selection
            default_scenes: list[str] = []
            if existing_selections is None:
                # Select all for initial setup
                default_scenes = list(scene_options.keys())
            else:
                # Keep existing selections
                default_scenes = [
                    unique_id
                    for unique_id in existing_scene_ids
                    if unique_id in scene_options
                ]

            schema_dict[vol.Optional("scenes", default=default_scenes)] = (
                cv.multi_select(scene_options)
            )

        return vol.Schema(schema_dict)

    @staticmethod
    def filter_selected_entities(
        user_input: dict[str, Any],
        discovered_entities: dict[
            str, list[DeviceType] | list[GroupType] | list[SceneType]
        ],
    ) -> ConfigData:
        """Filter selected entities from user input."""
        selected: ConfigData = {}

        # Filter devices
        if "devices" in user_input and "devices" in discovered_entities:
            selected_ids = user_input["devices"]
            devices = cast("list[DeviceType]", discovered_entities["devices"])
            selected["devices"] = [
                device for device in devices if device["unique_id"] in selected_ids
            ]

        # Filter groups
        if "groups" in user_input and "groups" in discovered_entities:
            selected_ids = user_input["groups"]
            groups = cast("list[GroupType]", discovered_entities["groups"])
            selected["groups"] = [
                group for group in groups if group["unique_id"] in selected_ids
            ]

        # Filter scenes
        if "scenes" in user_input and "scenes" in discovered_entities:
            selected_ids = user_input["scenes"]
            scenes = cast("list[SceneType]", discovered_entities["scenes"])
            selected["scenes"] = [
                scene for scene in scenes if scene["unique_id"] in selected_ids
            ]

        return selected
