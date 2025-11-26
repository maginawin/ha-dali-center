"""Config flow for the Dali Center integration."""

import asyncio
import logging
from typing import Any

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
from PySrDaliGateway.helper import is_light_device
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
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import CONF_SERIAL_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Reload timing constants (in seconds)
RELOAD_UNLOAD_DELAY = 0.5
RELOAD_SETUP_DELAY = 1.0

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("refresh", default=False): bool,
        vol.Optional("batch_configure", default=False): bool,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for Dali Center."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry
        self._selected_devices: list[str] = []

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

        if user_input.get("batch_configure", False):
            return await self.async_step_batch_configure()

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

    async def async_step_batch_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle batch device configuration step."""
        errors: dict[str, str] = {}

        if not hasattr(self._config_entry, "runtime_data"):
            errors["base"] = "gateway_not_found"
            return self.async_show_form(
                step_id="batch_configure",
                errors=errors,
                data_schema=vol.Schema({}),
            )

        devices = self._config_entry.runtime_data.devices
        light_devices = [dev for dev in devices if is_light_device(dev.dev_type)]

        if not light_devices:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="batch_configure",
                errors=errors,
                data_schema=vol.Schema({}),
            )

        if user_input is not None:
            # Store selected devices and move to parameter configuration
            self._selected_devices = user_input.get("devices", [])
            if not self._selected_devices:
                errors["devices"] = "no_devices_selected"
            else:
                return await self.async_step_batch_configure_params()

        # Create device selection options
        device_options = {
            dev.dev_id: f"{dev.name} (Ch{dev.channel}:{dev.address})"
            for dev in light_devices
        }

        return self.async_show_form(
            step_id="batch_configure",
            data_schema=vol.Schema(
                {
                    vol.Required("devices"): vol.All(
                        cv.multi_select(device_options), vol.Length(min=1)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_batch_configure_params(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle parameter configuration for selected devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Apply parameters to all selected devices
            devices = self._config_entry.runtime_data.devices
            device_map = {dev.dev_id: dev for dev in devices}

            success_count = 0
            failed_devices = []

            for dev_id in self._selected_devices:
                device = device_map.get(dev_id)
                if not device:
                    continue

                try:
                    params = {}
                    if user_input.get("set_fade_time", False):
                        params["fade_time"] = user_input["fade_time"]
                    if user_input.get("set_fade_rate", False):
                        params["fade_rate"] = user_input["fade_rate"]
                    if user_input.get("set_min_brightness", False):
                        params["min_brightness"] = user_input["min_brightness"]
                    if user_input.get("set_max_brightness", False):
                        params["max_brightness"] = user_input["max_brightness"]

                    if params:
                        device.set_device_parameters(params)
                        success_count += 1
                except Exception:
                    _LOGGER.exception("Failed to set parameters for device %s", dev_id)
                    failed_devices.append(device.name)

            # Show result
            result_message = f"Successfully configured {success_count} device(s).\n"
            if failed_devices:
                result_message += f"\nFailed devices: {', '.join(failed_devices)}"

            return self.async_show_form(
                step_id="batch_configure_result",
                data_schema=vol.Schema({}),
                description_placeholders={"result_message": result_message},
            )

        # Show parameter configuration form
        return self.async_show_form(
            step_id="batch_configure_params",
            data_schema=vol.Schema(
                {
                    vol.Optional("set_fade_time", default=False): bool,
                    vol.Optional("fade_time", default=7): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=15)
                    ),
                    vol.Optional("set_fade_rate", default=False): bool,
                    vol.Optional("fade_rate", default=7): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=15)
                    ),
                    vol.Optional("set_min_brightness", default=False): bool,
                    vol.Optional("min_brightness", default=10): vol.All(
                        vol.Coerce(int), vol.Range(min=10, max=1000)
                    ),
                    vol.Optional("set_max_brightness", default=False): bool,
                    vol.Optional("max_brightness", default=1000): vol.All(
                        vol.Coerce(int), vol.Range(min=10, max=1000)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_batch_configure_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display batch configuration result."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="batch_configure_result",
            data_schema=vol.Schema({}),
        )


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
