"""Config flow for the Dali Center integration."""

import asyncio
import logging
from typing import Any

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Reload timing constants (in seconds)
RELOAD_UNLOAD_DELAY = 0.5
RELOAD_SETUP_DELAY = 1.0

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("refresh", default=False): bool,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Dali Center."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def _reload_with_delay(self) -> bool:
        try:
            await self.hass.config_entries.async_unload(self._config_entry.entry_id)
            await asyncio.sleep(RELOAD_UNLOAD_DELAY)

            result = await self.hass.config_entries.async_setup(
                self._config_entry.entry_id
            )

            if not result:
                return False

            await asyncio.sleep(RELOAD_SETUP_DELAY)

        except (OSError, ValueError, RuntimeError):
            _LOGGER.exception("Error during config entry reload")
            return False

        return True

    async def async_step_init(
        self, user_input: dict[str, bool] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the options flow."""
        if not user_input:
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, {}),
            )

        if user_input.get("refresh", False):
            return await self.async_step_refresh()

        return self.async_create_entry(data={})

    async def async_step_refresh(self) -> ConfigFlowResult:
        """Refresh gateway IP, devices, groups, and scenes."""
        errors: dict[str, str] = {}

        try:
            current_sn = self._config_entry.data[CONF_SERIAL_NUMBER]

            if hasattr(self._config_entry, "runtime_data"):
                gateway: DaliGateway = self._config_entry.runtime_data.gateway
                await gateway.disconnect()

            discovery = DaliGatewayDiscovery()
            discovered_gateways = await discovery.discover_gateways(current_sn)

            if not discovered_gateways:
                _LOGGER.warning("Gateway %s not found during refresh", current_sn)
                errors["base"] = "gateway_not_found"
                return self.async_show_form(
                    step_id="refresh",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            updated_gateway = discovered_gateways[0]

            current_data = dict(self._config_entry.data)
            current_data[CONF_HOST] = updated_gateway.gw_ip

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=current_data
            )

            _LOGGER.info(
                "Gateway %s refreshed with IP %s", current_sn, updated_gateway.gw_ip
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
                    device.id,
                )
                device_reg.async_remove_device(device.id)

            entities_to_remove = er.async_entries_for_config_entry(
                entity_reg, self._config_entry.entry_id
            )

            for entity in entities_to_remove:
                _LOGGER.debug("Removing entity %s before reload", entity.entity_id)
                entity_reg.async_remove(entity.entity_id)

            # Wait for reload to complete
            reload_success = await self._reload_with_delay()

            if not reload_success:
                _LOGGER.error("Failed to reload integration after refresh")
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="refresh",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            return self.async_show_form(
                step_id="refresh_result",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "gateway_sn": current_sn,
                    "new_ip": updated_gateway.gw_ip,
                    "result_message": (
                        f"Gateway {current_sn} has been refreshed.\n"
                        f"IP address: {updated_gateway.gw_ip}\n\n"
                        "All devices, groups, and scenes have been re-discovered."
                    ),
                },
            )

        except Exception:
            _LOGGER.exception("Error refreshing gateway")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="refresh",
                errors=errors,
                data_schema=vol.Schema({}),
            )

    async def async_step_refresh_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the refresh result step."""
        if user_input is None:
            return self.async_show_form(
                step_id="refresh_result",
                data_schema=vol.Schema({}),
            )

        return self.async_create_entry(data={})


class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dali Center."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._gateways: list[DaliGateway] = []
        self._selected_gateway: DaliGateway | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return await self.async_step_discovery()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "message": (
                    "**Three-step process:**\n\n"
                    "1. Ensure the gateway is powered and on the same network.\n"
                    "2. Select **Submit** to start discovery (searches for up to 3 minutes)\n"
                    "3. While discovery is in progress, press the **Reset** button on your DALI gateway device **once**.\n\n"
                    "The gateway will respond immediately after the button press."
                )
            },
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the discovery step."""
        errors: dict[str, str] = {}

        if discovery_info is not None:
            if "selected_gateway" not in discovery_info:
                self._gateways = []
                return await self.async_step_discovery()

            selected_gateway: DaliGateway | None = next(
                (
                    gateway
                    for gateway in self._gateways
                    if gateway.gw_sn == discovery_info["selected_gateway"]
                ),
                None,
            )

            if selected_gateway:
                try:
                    await selected_gateway.connect()
                    await selected_gateway.disconnect()

                    return self.async_create_entry(
                        title=selected_gateway.name or selected_gateway.gw_sn,
                        data={
                            CONF_SERIAL_NUMBER: selected_gateway.gw_sn,
                            CONF_HOST: selected_gateway.gw_ip,
                            CONF_PORT: selected_gateway.port,
                            CONF_NAME: selected_gateway.name,
                            CONF_USERNAME: selected_gateway.username,
                            CONF_PASSWORD: selected_gateway.passwd,
                        },
                    )
                except DaliGatewayError:
                    _LOGGER.exception(
                        "Error connecting to gateway %s",
                        selected_gateway.gw_sn,
                    )
                    errors["base"] = "cannot_connect"
            else:
                _LOGGER.warning(
                    "Selected gateway ID %s not found in discovered list",
                    discovery_info["selected_gateway"],
                )
                errors["base"] = "device_not_found"

        if not self._gateways:
            try:
                discovered_gateways = await DaliGatewayDiscovery().discover_gateways()
            except DaliGatewayError:
                _LOGGER.exception("Error discovering gateways")
                errors["base"] = "discovery_failed"
                return self.async_show_form(
                    step_id="discovery",
                    errors=errors,
                    description_placeholders={
                        "message": (
                            "**Gateway discovery failed.**\n\n"
                            "Please check:\n"
                            "- Gateway is powered on\n"
                            "- Gateway is connected to the same network\n"
                            "- Reset button was pressed during discovery"
                        )
                    },
                    data_schema=vol.Schema({}),
                )

            configured_gateways = {
                entry.data.get(CONF_SERIAL_NUMBER) or entry.data.get("sn")
                for entry in self.hass.config_entries.async_entries(DOMAIN)
            }

            self._gateways = [
                gateway
                for gateway in discovered_gateways
                if gateway.gw_sn not in configured_gateways
            ]

            _LOGGER.info(
                "Found %d gateways, %d available after filtering configured",
                len(discovered_gateways),
                len(self._gateways),
            )

        if not self._gateways:
            return self.async_show_form(
                step_id="discovery",
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": (
                        "**No new gateways found.**\n\n"
                        "All discovered gateways are already configured.\n\n"
                        "If you want to reconfigure an existing gateway, remove it first and try again."
                    )
                },
                data_schema=vol.Schema({}),
            )

        gateway_options = {
            gw.gw_sn: f"{gw.name} ({gw.gw_ip})" if gw.name else gw.gw_ip
            for gw in self._gateways
        }

        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_gateway"): vol.In(gateway_options),
                }
            ),
            errors=errors,
            description_placeholders={
                "message": (
                    f"**Found {len(self._gateways)} gateway(s).**\n\n"
                    "Select a gateway to configure."
                )
            },
        )

    def is_matching(self, other_flow: "ConfigFlow") -> bool:
        """Check if another flow is matching this one."""
        return False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)
