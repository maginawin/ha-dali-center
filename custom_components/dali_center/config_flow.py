"""Config flow for the Dali Center integration."""

import logging
from typing import Any, Optional
import voluptuous as vol
import asyncio

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import device_registry as dr

from .types import ConfigData
from PySrDaliGateway import DaliGateway, DaliGatewayType
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
from .const import DOMAIN
from .config_flow_helpers.entity_helpers import EntityDiscoveryHelper
from .config_flow_helpers.ui_helpers import UIFormattingHelper

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("refresh_devices", default=False): bool,
        vol.Optional("refresh_groups", default=False): bool,
        vol.Optional("refresh_scenes", default=False): bool,
        vol.Optional("refresh_gateway_ip", default=False): bool
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Dali Center."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__()
        self._config_entry = config_entry
        self._refresh_devices = False
        self._refresh_groups = False
        self._refresh_scenes = False
        self._refresh_gateway_ip = False
        self._refresh_results: dict[str, Any] = {}
        self._discovered_entities: dict[str, list] = {}

    async def _reload_with_delay(self) -> bool:
        """Reload config entry with a delay to ensure clean state.

        Returns:
            bool: True if reload was successful, False otherwise
        """
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
            result = await self.hass.config_entries.async_setup(
                self._config_entry.entry_id
            )

            if result:
                _LOGGER.debug("Config entry reload completed successfully")
                # Wait a bit more for runtime_data to be fully initialized
                await asyncio.sleep(1.0)
                return True
            else:
                _LOGGER.error("Config entry setup failed")
                return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error(
                "Error during config entry reload: %s", e
            )
            return False

    async def async_step_init(
        self, user_input: dict[str, bool] | None = None
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
        self._refresh_gateway_ip = user_input.get(
            "refresh_gateway_ip", self._refresh_gateway_ip)

        # If IP refresh is requested, do it first
        if self._refresh_gateway_ip:
            return await self.async_step_refresh_gateway_ip()

        return await self.async_step_refresh()

    async def async_step_refresh(self) -> ConfigFlowResult:
        """Search for devices and automatically update configuration."""
        errors = {}

        try:
            _LOGGER.debug(
                "Searching for devices on gateway %s",
                self._config_entry.data["sn"]
            )

            if not self._config_entry.runtime_data:
                _LOGGER.warning(
                    "Gateway %s not found in runtime_data",
                    self._config_entry.data["sn"])
                return self.async_abort(reason="gateway_not_found")

            gateway: DaliGateway = self._config_entry.runtime_data.gateway

            # Discover entities based on user selection using helper
            discovered = await EntityDiscoveryHelper.discover_entities(
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
            selected = EntityDiscoveryHelper.filter_selected_entities(
                user_input, self._discovered_entities)

            # Calculate differences between current config and user selection
            self._refresh_results = UIFormattingHelper.\
                calculate_entity_differences(
                    dict(selected),
                    current_data,
                    self._refresh_devices,
                    self._refresh_groups,
                    self._refresh_scenes
                )

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

            # Wait for reload to complete
            await self._reload_with_delay()

            return await self.async_step_refresh_result()

        # Prepare schema with existing selections and diff display using helper
        current_data = dict(self._config_entry.data)
        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
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
                "diff_summary": UIFormattingHelper.format_discovery_summary(
                    self._discovered_entities,
                    self._refresh_devices,
                    self._refresh_groups,
                    self._refresh_scenes
                )}
        )

    async def async_step_refresh_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display refresh results."""
        if user_input is None:
            return self.async_show_form(
                step_id="refresh_result",
                description_placeholders={
                    "result_message": UIFormattingHelper.format_refresh_results(
                        self._refresh_results
                    )
                },
                data_schema=vol.Schema({}),
            )

        return self.async_create_entry(data={})

    async def async_step_refresh_gateway_ip(self) -> ConfigFlowResult:
        """Refresh gateway IP address by serial number discovery."""
        errors = {}

        try:
            _LOGGER.debug(
                "Refreshing IP for gateway %s",
                self._config_entry.data["sn"]
            )

            # Get current gateway serial number
            current_sn = self._config_entry.data["sn"]
            gateway: DaliGateway = self._config_entry.runtime_data.gateway
            await gateway.disconnect()

            # Perform discovery with serial number to get updated IP
            discovery = DaliGatewayDiscovery()
            discovered_gateways = await discovery.discover_gateways(current_sn)

            if not discovered_gateways:
                _LOGGER.warning(
                    "Gateway %s not found during IP refresh", current_sn)
                errors["base"] = "gateway_not_found"
                return self.async_show_form(
                    step_id="refresh_gateway_ip",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            # Get the first (and should be only) gateway found
            updated_gateway = discovered_gateways[0]

            # Update config entry with new IP
            current_data = dict(self._config_entry.data)
            current_data["gateway"]["gw_ip"] = updated_gateway["gw_ip"]

            # Update config entry
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=current_data
            )

            _LOGGER.info(
                "Gateway %s IP updated to %s",
                current_sn, updated_gateway["gw_ip"]
            )

            # Wait for reload to complete
            reload_success = await self._reload_with_delay()

            if not reload_success:
                _LOGGER.error("Failed to reload integration after IP update")
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="refresh_gateway_ip",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            # If other refreshes are also requested, continue to entity refresh
            if (self._refresh_devices or self._refresh_groups or
                    self._refresh_scenes):
                return await self.async_step_refresh()

            # Otherwise, show success result
            return self.async_show_form(
                step_id="refresh_gateway_ip_result",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "gateway_sn": current_sn,
                    "new_ip": updated_gateway["gw_ip"]
                }
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.error("Error refreshing gateway IP: %s", e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="refresh_gateway_ip",
                errors=errors,
                data_schema=vol.Schema({}),
            )

    async def async_step_refresh_gateway_ip_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display gateway IP refresh result."""
        if user_input is None:
            return self.async_show_form(
                step_id="refresh_gateway_ip_result",
                data_schema=vol.Schema({}),
            )

        return self.async_create_entry(data={})


# type: ignore[call-arg]
class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
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
        """Handle the initial step - show gateway discovery instructions."""
        if user_input is not None:
            # User confirmed, proceed to discovery
            return await self.async_step_discovery()

        # Show instructions to user before starting discovery
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "message": UIFormattingHelper.get_discovery_instructions()
            }
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle gateway discovery and selection step."""
        errors = {}

        if discovery_info is not None:
            # Check if this is a retry request (no gateway selection)
            if "selected_gateway" not in discovery_info:
                self._gateways = []
                return await self.async_step_discovery()

            # User selected a gateway, proceed to connection
            selected_gateway: Optional[DaliGatewayType] = next((
                gateway for gateway in self._gateways
                if gateway["gw_sn"] == discovery_info["selected_gateway"]
            ), None)

            if selected_gateway:
                self._selected_gateway = DaliGateway(selected_gateway)
                self._config_data = {
                    "sn": self._selected_gateway.gw_sn,
                    "gateway": self._selected_gateway.to_dict()
                }

                try:
                    await self._selected_gateway.connect()
                    return await self.async_step_configure_entities()
                except DaliGatewayError as e:
                    _LOGGER.error(
                        "Error connecting to gateway %s: %s",
                        self._selected_gateway.gw_sn, e
                    )
                    errors["base"] = "cannot_connect"
            else:
                _LOGGER.warning(
                    "Selected gateway ID %s not found in discovered list",
                    discovery_info["selected_gateway"]
                )
                errors["base"] = "device_not_found"

        # Perform gateway discovery if not already done
        if not self._gateways:
            _LOGGER.debug("Starting gateway discovery (3-minute timeout)")
            try:
                discovered_gateways = await DaliGatewayDiscovery()\
                    .discover_gateways()
            except DaliGatewayError as e:
                _LOGGER.error("Error discovering gateways: %s", e)
                errors["base"] = "discovery_failed"
                return self.async_show_form(
                    step_id="discovery",
                    errors=errors,
                    description_placeholders={
                        "message": UIFormattingHelper.
                            get_discovery_failed_message()
                    },
                    data_schema=vol.Schema({}),
                )

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

        # Handle case where no gateways were found
        if not self._gateways:
            _LOGGER.warning("No valid gateways found after discovery")
            return self.async_show_form(
                step_id="discovery",
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": UIFormattingHelper.get_no_gateways_message()
                },
                data_schema=vol.Schema({}),
            )

        # Show gateway selection
        _LOGGER.debug("Presenting gateway selection: %s", self._gateways)
        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_gateway"): vol.In(
                        UIFormattingHelper.format_gateway_options(
                            self._gateways)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "message": UIFormattingHelper.get_success_message(
                    len(self._gateways)
                )
            }
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
            # Filter selected entities using helper
            selected = EntityDiscoveryHelper.filter_selected_entities(
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

            # Discover all entities using helper
            self._discovered_entities = await EntityDiscoveryHelper.\
                discover_entities(
                    self._selected_gateway,
                    discover_devices=True,
                    discover_groups=True,
                    discover_scenes=True
                )

            # Disconnect from the gateway
            try:
                await self._selected_gateway.disconnect()
            except DaliGatewayError as e:
                _LOGGER.error(
                    "Error disconnecting from gateway %s: %s",
                    self._selected_gateway.gw_sn, e
                )
                errors["base"] = "cannot_disconnect"
                return self.async_show_form(
                    step_id="configure_entities",
                    errors=errors,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                _LOGGER.error(
                    "Error disconnecting from gateway %s: %s",
                    self._selected_gateway.gw_sn, e
                )
                errors["base"] = "cannot_disconnect"
                return self.async_show_form(
                    step_id="configure_entities",
                    errors=errors,
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            _LOGGER.warning("Error searching entities on gateway %s: %s",
                            self._config_data["sn"], e)
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="configure_entities",
                errors=errors,
            )

        schema = EntityDiscoveryHelper.prepare_entity_selection_schema(
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
