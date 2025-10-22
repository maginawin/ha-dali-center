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

from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("refresh_gateway_ip", default=False): bool,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Dali Center."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        super().__init__()
        self._config_entry = config_entry

    async def _reload_with_delay(self) -> bool:
        try:
            _LOGGER.debug("Unloading config entry %s", self._config_entry.entry_id)
            await self.hass.config_entries.async_unload(self._config_entry.entry_id)

            # Wait a moment to ensure everything is cleaned up
            await asyncio.sleep(0.5)

            # Then reload the entry
            _LOGGER.debug(
                "Setting up config entry %s with new configuration",
                self._config_entry.entry_id,
            )
            result = await self.hass.config_entries.async_setup(
                self._config_entry.entry_id
            )

            if not result:
                _LOGGER.error("Config entry setup failed")
                return False

            _LOGGER.debug("Config entry reload completed successfully")
            # Wait a bit more for runtime_data to be fully initialized
            await asyncio.sleep(1.0)

        except Exception:
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

        # Only IP refresh is supported
        if user_input.get("refresh_gateway_ip", False):
            return await self.async_step_refresh_gateway_ip()

        # No action selected, just close
        return self.async_create_entry(data={})

    async def async_step_refresh_gateway_ip(self) -> ConfigFlowResult:
        """Refresh gateway IP address by serial number discovery."""
        errors: dict[str, str] = {}

        try:
            current_sn = self._config_entry.data.get(
                CONF_SERIAL_NUMBER
            ) or self._config_entry.data.get("sn")
            _LOGGER.debug("Refreshing IP for gateway %s", current_sn)

            if hasattr(self._config_entry, "runtime_data"):
                gateway: DaliGateway = self._config_entry.runtime_data.gateway
                await gateway.disconnect()
                _LOGGER.debug("Disconnected existing gateway connection")

            discovery = DaliGatewayDiscovery()
            discovered_gateways = await discovery.discover_gateways(current_sn)

            if not discovered_gateways:
                _LOGGER.warning("Gateway %s not found during IP refresh", current_sn)
                errors["base"] = "gateway_not_found"
                return self.async_show_form(
                    step_id="refresh_gateway_ip",
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
                "Gateway %s IP updated to %s", current_sn, updated_gateway.gw_ip
            )

            reload_success = await self._reload_with_delay()

            if not reload_success:
                _LOGGER.error("Failed to reload integration after IP update")
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="refresh_gateway_ip",
                    errors=errors,
                    data_schema=vol.Schema({}),
                )

            # IP refresh successful, show result
            return self.async_show_form(
                step_id="refresh_gateway_ip_result",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "gateway_sn": current_sn or "",
                    "new_ip": updated_gateway.gw_ip,
                },
            )

        except Exception:
            _LOGGER.exception("Error refreshing gateway IP")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="refresh_gateway_ip",
                errors=errors,
                data_schema=vol.Schema({}),
            )

    async def async_step_refresh_gateway_ip_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the gateway IP refresh result step."""
        if user_input is None:
            return self.async_show_form(
                step_id="refresh_gateway_ip_result",
                data_schema=vol.Schema({}),
            )

        return self.async_create_entry(data={})


class DaliCenterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dali Center."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
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
                "message": "Click SUBMIT to start gateway discovery (takes up to 3 minutes)."
            },
        )

    async def async_step_discovery(
        self, discovery_info: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the discovery step."""
        errors: dict[str, str] = {}

        if discovery_info is not None:
            # Check if this is a retry request (no gateway selection)
            if "selected_gateway" not in discovery_info:
                self._gateways = []
                return await self.async_step_discovery()

            # User selected a gateway
            selected_gateway: DaliGateway | None = next(
                (
                    gateway
                    for gateway in self._gateways
                    if gateway.gw_sn == discovery_info["selected_gateway"]
                ),
                None,
            )

            if selected_gateway:
                # Test connection and create entry
                try:
                    await selected_gateway.connect()
                    await selected_gateway.disconnect()

                    # Create config entry with gateway info only
                    return self.async_create_entry(
                        title=selected_gateway.name or selected_gateway.gw_sn,
                        data={
                            CONF_SERIAL_NUMBER: selected_gateway.gw_sn,
                            CONF_HOST: selected_gateway.gw_ip,
                            CONF_PORT: selected_gateway.port,
                            CONF_NAME: selected_gateway.name or "",
                            CONF_USERNAME: selected_gateway.username or "",
                            CONF_PASSWORD: selected_gateway.passwd or "",
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

        # Perform gateway discovery if not already done
        if not self._gateways:
            _LOGGER.debug("Starting gateway discovery (3-minute timeout)")
            try:
                discovered_gateways = await DaliGatewayDiscovery().discover_gateways()
            except DaliGatewayError:
                _LOGGER.exception("Error discovering gateways")
                errors["base"] = "discovery_failed"
                return self.async_show_form(
                    step_id="discovery",
                    errors=errors,
                    description_placeholders={
                        "message": "Gateway discovery failed. Please ensure gateways are powered on and connected to the network."
                    },
                    data_schema=vol.Schema({}),
                )

            # Filter out already configured gateways
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

        # Handle case where no gateways were found
        if not self._gateways:
            _LOGGER.warning("No valid gateways found after discovery")
            return self.async_show_form(
                step_id="discovery",
                errors={"base": "no_devices_found"},
                description_placeholders={
                    "message": "No new gateways found. All discovered gateways are already configured."
                },
                data_schema=vol.Schema({}),
            )

        # Format gateway options for dropdown
        gateway_options = {
            gw.gw_sn: f"{gw.name} ({gw.gw_ip})" if gw.name else gw.gw_ip
            for gw in self._gateways
        }

        _LOGGER.debug("Presenting gateway selection: %s", self._gateways)
        return self.async_show_form(
            step_id="discovery",
            data_schema=vol.Schema(
                {
                    vol.Required("selected_gateway"): vol.In(gateway_options),
                }
            ),
            errors=errors,
            description_placeholders={
                "message": f"Found {len(self._gateways)} gateway(s). Select one to configure."
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
