"""Config flow for the Dali Center integration."""

import logging
from typing import Any, Optional
import voluptuous as vol
import asyncio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .helper import find_set_differences
from .types import ConfigData
from PySrDaliGateway import DaliGateway, DaliGatewayType, DeviceType, GroupType, SceneType
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("refresh_devices", default=False): bool,
        vol.Optional("refresh_groups", default=False): bool,
        vol.Optional("refresh_scenes", default=False): bool
    }
)


class EntityDiscoveryMixin:
    """Mixin class for entity discovery and selection logic."""

    async def _discover_entities(
        self,
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
            except Exception as e:  # pylint: disable=broad-exception-caught
                _LOGGER.warning(
                    "Error discovering devices on gateway %s: %s",
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
                    "Error discovering groups on gateway %s: %s",
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
                    "Error discovering scenes on gateway %s: %s", 
                    gateway.gw_sn, e
                )
                discovered["scenes"] = []

        return discovered

    def _prepare_entity_selection_schema(
        self,
        devices: list,
        groups: list,
        scenes: list,
        existing_selections: Optional[dict[str, list]] = None,
        show_diff: bool = False
    ) -> vol.Schema:
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

            # Default selection
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

    def _filter_selected_entities(
        self,
        user_input: dict[str, Any],
        discovered_entities: dict[str, list]
    ) -> ConfigData:
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


class OptionsFlowHandler(config_entries.OptionsFlow, EntityDiscoveryMixin):
    """Handle a options flow for Dali Center."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry
        self._refresh_devices = False
        self._refresh_groups = False
        self._refresh_scenes = False
        self._refresh_results: dict[str, Any] = {}
        self._discovered_entities: dict[str, list] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        _LOGGER.warning("OptionsFlowHandler: async_step_init %s", user_input)

        if not user_input:
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(
                    OPTIONS_SCHEMA, {}
                ),
            )

        _LOGGER.debug("User input: %s", user_input)

        self._refresh_devices = user_input.get(
            "refresh_devices", self._refresh_devices)
        self._refresh_groups = user_input.get(
            "refresh_groups", self._refresh_groups)
        self._refresh_scenes = user_input.get(
            "refresh_scenes", self._refresh_scenes)

        return await self.async_step_refresh()

    async def async_step_refresh(self) -> ConfigFlowResult:
        """Search for devices and automatically update configuration."""
        errors = {}

        try:
            _LOGGER.debug(
                "Searching for devices on gateway %s",
                self._config_entry.data["sn"]
            )

            if self._config_entry.entry_id not in self.hass.data[DOMAIN]:
                _LOGGER.warning(
                    "Gateway %s not found in hass.data[DOMAIN]",
                    self._config_entry.data["sn"])
                return self.async_abort(reason="gateway_not_found")

            gateway: DaliGateway = self.hass.data[DOMAIN][
                self._config_entry.entry_id]

            # Discover entities based on user selection
            discovered = await self._discover_entities(
                gateway,
                discover_devices=self._refresh_devices,
                discover_groups=self._refresh_groups,
                discover_scenes=self._refresh_scenes
            )

            # Store discovered entities for next step
            self._discovered_entities = discovered

            # Go to entity selection step
            return await self.async_step_select_entities()

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Error searching for devices on gateway %s: %s",
                            self._config_entry.data["sn"], e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="refresh",
                errors=errors,
            )

    async def async_step_select_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow user to select entities with diff display."""
        if user_input is not None:
            current_data = dict(self._config_entry.data)
            selected = self._filter_selected_entities(
                user_input, self._discovered_entities)

            # Calculate differences between current config and user selection
            self._calculate_entity_differences(selected, current_data)

            # Update config data with selected entities
            updated_data = {**current_data, **selected}

            # Update config entry
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=updated_data
            )

            # Remove all devices associated with this config entry before reload
            device_reg = dr.async_get(self.hass)
            entity_reg = er.async_get(self.hass)

            # First, get all devices for this config entry
            devices_to_remove = dr.async_entries_for_config_entry(
                device_reg, self._config_entry.entry_id
            )

            # Remove all devices (this will also remove associated entities)
            for device in devices_to_remove:
                _LOGGER.debug(
                    "Removing device %s (%s) before reload",
                    device.name or "Unknown",
                    device.id
                )
                device_reg.async_remove_device(device.id)

            entities_to_remove = er.async_entries_for_config_entry(
                entity_reg, self._config_entry.entry_id
            )

            for entity in entities_to_remove:
                _LOGGER.debug(
                    "Removing entity %s before reload",
                    entity.entity_id
                )
                entity_reg.async_remove(entity.entity_id)

            async def _reload_with_delay() -> None:
                """Reload config entry with a delay to ensure clean state."""
                try:
                    _LOGGER.debug(
                        "Unloading config entry %s",
                        self._config_entry.entry_id
                    )
                    await self.hass.config_entries.async_unload(
                        self._config_entry.entry_id
                    )

                    # Wait a moment to ensure everything is cleaned up
                    await asyncio.sleep(0.5)

                    # Then reload the entry
                    _LOGGER.debug(
                        "Setting up config entry %s with new configuration",
                        self._config_entry.entry_id
                    )
                    await self.hass.config_entries.async_setup(
                        self._config_entry.entry_id
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    _LOGGER.error(
                        "Error during config entry reload: %s", e
                    )

            # Schedule the reload
            self.hass.async_create_task(_reload_with_delay())

            return await self.async_step_refresh_result()

        # Prepare schema with existing selections and diff display
        current_data = dict(self._config_entry.data)
        schema = self._prepare_entity_selection_schema(
            devices=self._discovered_entities.get("devices", []),
            groups=self._discovered_entities.get("groups", []),
            scenes=self._discovered_entities.get("scenes", []),
            existing_selections=current_data,
            show_diff=True
        )

        return self.async_show_form(
            step_id="select_entities",
            data_schema=schema,
            description_placeholders={
                "diff_summary": self._format_discovery_summary()}
        )

    def _format_discovery_summary(self) -> str:
        """Format a summary of discovered entities."""
        entity_types = [
            ("devices", self._refresh_devices),
            ("groups", self._refresh_groups),
            ("scenes", self._refresh_scenes)
        ]

        summary = []
        for entity_type, should_refresh in entity_types:
            if should_refresh and entity_type in self._discovered_entities:
                total = len(self._discovered_entities[entity_type])
                summary.append(f"Discovered {entity_type.title()}: {total}")

        return "\n".join(summary) if summary else "No entities discovered"

    async def async_step_refresh_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display refresh results."""
        if user_input is None:
            return self.async_show_form(
                step_id="refresh_result",
                description_placeholders={
                    "result_message": self._format_refresh_results()
                },
                data_schema=vol.Schema({}),
            )

        return self.async_create_entry(data={})

    def _format_refresh_results(self) -> str:
        """Format refresh results for display."""
        if not hasattr(self, "_refresh_results"):
            return "No items refreshed"

        results = self._refresh_results
        result_parts = []

        # Define entity types and their formatters
        entity_configs = [
            ("devices", "name", "unique_id"),
            ("groups", "name", lambda g: f"Channel: {
                g.get("channel", "N/A")
            }, Group: {g.get("id", "N/A")}"),
            ("scenes", "name", lambda s: f"Channel: {
                s.get("channel", "N/A")
            }, Scene: {s.get("id", "N/A")}")
        ]

        for entity_type, name_key, id_formatter in entity_configs:
            count_key = f"{entity_type}_count"
            if count_key in results:
                result_parts.append(
                    f"Total {entity_type.title()}: {results[count_key]}")
                details = self._format_added_removed(
                    results, entity_type, name_key, id_formatter
                )
                if details:
                    result_parts.append(details)
                result_parts.append("")  # Empty line

        return "\n".join(result_parts).strip() or "No items refreshed"

    def _format_added_removed(
        self, results: dict, prefix: str, name_key: str,
        id_formatter: object
    ) -> str:
        """Format added and removed items."""
        def format_items(items: list, action: str) -> list[str]:
            if not items:
                return [f"No {prefix} {action}"]

            lines = [f"{action.title()} {prefix.title()} ({len(items)}):"]
            for item in items:
                id_str = (
                    id_formatter(item) if callable(id_formatter)
                    else f"ID: {item.get(id_formatter, "N/A")}"
                )
                lines.append(f"  - {item.get(name_key, "Unnamed")} ({id_str})")
            lines.append("")
            return lines

        message_parts = []
        message_parts.extend(format_items(
            results.get(f"{prefix}_added", []), "added"))
        message_parts.extend(format_items(
            results.get(f"{prefix}_removed", []), "removed"))

        return "\n".join(message_parts)

    def _calculate_entity_differences(
        self,
        selected: ConfigData,
        current_data: dict[str, Any]
    ) -> None:
        """Calculate differences between selected and current entities."""
        self._refresh_results = {}

        # Process devices
        if self._refresh_devices and "devices" in selected:
            added, removed = find_set_differences(
                selected["devices"],
                current_data.get("devices", []),
                "unique_id"
            )
            self._refresh_results["devices_added"] = added
            self._refresh_results["devices_removed"] = removed
            self._refresh_results["devices_count"] = len(selected["devices"])

        # Process groups
        if self._refresh_groups and "groups" in selected:
            added, removed = find_set_differences(
                selected["groups"],
                current_data.get("groups", []),
                "unique_id"
            )
            self._refresh_results["groups_added"] = added
            self._refresh_results["groups_removed"] = removed
            self._refresh_results["groups_count"] = len(selected["groups"])

        # Process scenes
        if self._refresh_scenes and "scenes" in selected:
            added, removed = find_set_differences(
                selected["scenes"],
                current_data.get("scenes", []),
                "unique_id"
            )
            self._refresh_results["scenes_added"] = added
            self._refresh_results["scenes_removed"] = removed
            self._refresh_results["scenes_count"] = len(selected["scenes"])


class DaliCenterConfigFlow(
    ConfigFlow, EntityDiscoveryMixin, domain=DOMAIN
):  # type: ignore[call-arg]
    """Handle a config flow for Dali Center."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._gateways: list[DaliGatewayType] = []
        self._discovered_entities: dict[str, list] = {}
        self._selected_gateway: Optional[DaliGateway] = None
        self._config_data: ConfigData = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step to select a gateway."""
        errors = {}

        if user_input is not None:
            selected_gateway: Optional[DaliGatewayType] = next((
                gateway for gateway in self._gateways
                if gateway["gw_sn"] == user_input["selected_gateway"]
            ), None)

            if selected_gateway:
                self._selected_gateway = DaliGateway(selected_gateway)
                self._config_data = {
                    "sn": self._selected_gateway.gw_sn,
                    "gateway": self._selected_gateway.to_dict()
                }

                await self._selected_gateway.connect()
                return await self.async_step_configure_entities()
            else:
                _LOGGER.warning(
                    "Selected gateway ID %s not found in discovered list",
                    user_input["selected_gateway"]
                )
                errors["base"] = "device_not_found"

        if not self._gateways:
            _LOGGER.debug("No gateways cached, starting discovery")
            discovered_gateways = await DaliGatewayDiscovery()\
                .discover_gateways()

            # Filter out already configured gateways
            configured_gateways = {
                entry.data["sn"]
                for entry in self.hass.config_entries.async_entries(DOMAIN)
            }

            self._gateways = [
                gateway for gateway in discovered_gateways
                if gateway["gw_sn"] not in configured_gateways
            ]

            _LOGGER.info(
                "Found %d gateways, %d available after filtering configured",
                len(discovered_gateways),
                len(self._gateways)
            )

        if not self._gateways:
            _LOGGER.warning("No valid gateways found after parsing")
            return self.async_abort(reason="no_devices_found")

        _LOGGER.debug("Presenting gateway selection: %s", self._gateways)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_gateway"): vol.In({
                        gateway["gw_sn"]: gateway["name"]
                        for gateway in self._gateways
                    }),
                }
            ),
            errors=errors,
        )

    async def async_step_configure_entities(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Search for devices, groups, and scenes"""
        errors = {}

        if not self._selected_gateway:
            _LOGGER.error("No selected gateway found")
            return self.async_abort(reason="no_gateway_selected")

        if user_input is not None:
            # Filter selected entities
            selected = self._filter_selected_entities(
                user_input,
                self._discovered_entities
            )

            self._config_data.update(selected)

            # Create the config entry
            return self.async_create_entry(
                title=self._selected_gateway.name,
                data=self._config_data,
            )

        try:
            _LOGGER.debug(
                "Searching for entities on gateway %s",
                self._config_data["sn"]
            )

            # Discover all entities
            self._discovered_entities = await self._discover_entities(
                self._selected_gateway,
                discover_devices=True,
                discover_groups=True,
                discover_scenes=True
            )

            # Disconnect from the gateway
            await self._selected_gateway.disconnect()

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Error searching entities on gateway %s: %s",
                            self._config_data["sn"], e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="configure_entities",
                errors=errors,
            )

        # Prepare selection schema with all entities selected by default
        schema = self._prepare_entity_selection_schema(
            devices=self._discovered_entities.get("devices", []),
            groups=self._discovered_entities.get("groups", []),
            scenes=self._discovered_entities.get("scenes", []),
            existing_selections=None,
            show_diff=False
        )

        if not schema.schema:
            _LOGGER.warning("No entities found on the gateway")
            return self.async_abort(reason="no_entities_found")

        return self.async_show_form(
            step_id="configure_entities",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)
