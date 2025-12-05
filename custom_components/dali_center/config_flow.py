"""Config flow for the Dali Center integration."""

import asyncio
import logging
from typing import Any

from PySrDaliGateway import DaliGateway
from PySrDaliGateway.discovery import DaliGatewayDiscovery
from PySrDaliGateway.exceptions import DaliGatewayError
from PySrDaliGateway.helper import is_light_device
from PySrDaliGateway.types import DeviceParamCommand, DeviceParamType
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
        self._pending_batch_config: dict[str, Any] | None = None
        self._batch_config_executed = False
        self._batch_config_result_message: str | None = None

    @staticmethod
    def _device_label(device: Any) -> str:
        """Return a safe device label."""
        name = getattr(device, "name", None)
        dev_id = getattr(device, "dev_id", None)
        return str(name or dev_id or "Unknown device")

    @staticmethod
    def _format_parameter_summary(params: DeviceParamType) -> str:
        """Format parameter dictionary as a readable summary."""
        param_lines: list[str] = []
        if "fade_time" in params:
            param_lines.append(f"- Fade time: {params['fade_time']}")
        if "fade_rate" in params:
            param_lines.append(f"- Fade rate: {params['fade_rate']}")
        if "min_brightness" in params:
            param_lines.append(f"- Min brightness: {params['min_brightness']}")
        if "max_brightness" in params:
            param_lines.append(f"- Max brightness: {params['max_brightness']}")

        return "\n".join(param_lines) if param_lines else "(none)"

    async def _validate_batch_input(
        self,
        user_input: dict[str, Any],
        light_devices: list[Any],
        groups: list[Any],
        gateway_target: str,
    ) -> tuple[dict[str, str], DeviceParamType, list[Any]]:
        """Validate batch configure input and build params and targets."""
        errors: dict[str, str] = {}
        params: DeviceParamType = {}
        selected_targets = user_input.get("targets", [])
        fade_time: int | None = None
        fade_rate: int | None = None
        min_brightness: int | None = None
        max_brightness: int | None = None

        def _parse_int(field: str, min_value: int, max_value: int) -> int | None:
            raw = user_input.get(field, "")
            if raw in ("", None):
                return None
            try:
                value = int(raw)
            except (TypeError, ValueError):
                errors[field] = "invalid_format"
                return None
            if not min_value <= value <= max_value:
                errors[field] = "out_of_range"
                return None
            return value

        fade_time = _parse_int("fade_time", 0, 15)
        fade_rate = _parse_int("fade_rate", 0, 15)
        min_brightness = _parse_int("min_brightness", 10, 1000)
        max_brightness = _parse_int("max_brightness", 10, 1000)

        if (
            not errors.get("min_brightness")
            and not errors.get("max_brightness")
            and min_brightness is not None
            and max_brightness is not None
            and min_brightness > max_brightness
        ):
            errors["max_brightness"] = "min_max_conflict"

        if not errors:
            if fade_time is not None:
                params["fade_time"] = fade_time
            if fade_rate is not None:
                params["fade_rate"] = fade_rate
            if min_brightness is not None:
                params["min_brightness"] = min_brightness
            if max_brightness is not None:
                params["max_brightness"] = max_brightness

        if (
            not errors
            and fade_time is None
            and fade_rate is None
            and min_brightness is None
            and max_brightness is None
        ):
            errors["base"] = "no_parameters_selected"

        if not selected_targets:
            errors["targets"] = "no_targets_selected"

        target_devices: dict[str, Any] = {}
        if not errors:
            device_map = {f"device:{dev.dev_id}": dev for dev in light_devices}
            devices_by_unique_id = {dev.unique_id: dev for dev in light_devices}
            group_map = {f"group:{group.unique_id}": group for group in groups}

            if gateway_target in selected_targets:
                for device in light_devices:
                    target_devices[device.dev_id] = device

            for target_id in selected_targets:
                if target_id in device_map:
                    device = device_map[target_id]
                    target_devices[device.dev_id] = device

            for target_id in selected_targets:
                if target_id not in group_map:
                    continue

                group = group_map[target_id]
                for member in group.devices:
                    member_unique_id = member.get("unique_id")
                    if member_unique_id and member_unique_id in devices_by_unique_id:
                        device = devices_by_unique_id[member_unique_id]
                        target_devices[device.dev_id] = device

            if not target_devices:
                errors["targets"] = "no_targets_available"

        return errors, params, list(target_devices.values())

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
        """Handle batch configuration for devices, groups, and gateway broadcast."""
        errors: dict[str, str] = {}
        self._pending_batch_config = None
        self._batch_config_executed = False
        self._batch_config_result_message = None

        runtime_data = getattr(self._config_entry, "runtime_data", None)
        if runtime_data is None:
            errors["base"] = "gateway_not_found"
            return self.async_show_form(
                step_id="batch_configure",
                errors=errors,
                data_schema=vol.Schema({}),
            )

        gateway = runtime_data.gateway
        devices = runtime_data.devices
        groups = runtime_data.groups
        light_devices = [dev for dev in devices if is_light_device(dev.dev_type)]

        if not light_devices:
            errors["base"] = "no_devices_found"
            return self.async_show_form(
                step_id="batch_configure",
                errors=errors,
                data_schema=vol.Schema({}),
            )

        gateway_target = f"gateway:{gateway.gw_sn}"
        target_options: dict[str, str] = {
            gateway_target: f"{gateway.name or gateway.gw_sn} (broadcast)"
        }
        device_options = {
            f"device:{dev.dev_id}": (
                f"{dev.name or 'Device'} (Ch{dev.channel}:{dev.address})"
            )
            for dev in light_devices
        }
        group_options = {
            f"group:{group.unique_id}": (
                f"{group.name or 'Group'} (Ch{group.channel} G{group.group_id})"
            )
            for group in groups
        }

        target_options.update(device_options)
        target_options.update(group_options)

        data_schema = vol.Schema(
            {
                vol.Required("targets"): vol.All(
                    cv.multi_select(target_options), vol.Length(min=1)
                ),
                vol.Optional("fade_time", default=""): cv.string,
                vol.Optional("fade_rate", default=""): cv.string,
                vol.Optional("min_brightness", default=""): cv.string,
                vol.Optional("max_brightness", default=""): cv.string,
            }
        )

        if user_input is not None:
            (
                validation_errors,
                params,
                target_devices,
            ) = await self._validate_batch_input(
                user_input, light_devices, groups, gateway_target
            )
            errors.update(validation_errors)

            if not errors:
                self._pending_batch_config = {
                    "gateway": gateway,
                    "devices": target_devices or [],
                    "params": params,
                }
                return await self.async_step_batch_configure_result()

        # Placeholder text communicates "blank = keep current" in the UI.
        return self.async_show_form(
            step_id="batch_configure",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "fade_range": "0-15",
                "brightness_range": "10-1000",
            },
        )

    async def async_step_batch_configure_result(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Display batch configuration result."""
        if self._pending_batch_config is None and not self._batch_config_result_message:
            return self.async_create_entry(data={})

        if not self._batch_config_executed:
            # Show preview before execution.
            if user_input is None:
                if self._pending_batch_config is None:
                    return self.async_create_entry(data={})
                preview_params: DeviceParamType = self._pending_batch_config["params"]
                preview_devices = self._pending_batch_config["devices"]
                param_summary = (
                    "Parameters to apply:\n"
                    + self._format_parameter_summary(preview_params)
                )

                planned_message = (
                    f"{param_summary}\n\n"
                    f"Will update {len(preview_devices)} device(s) with selected parameters."
                )
                if preview_devices:
                    planned_message += f"\nDevices: {', '.join(self._device_label(device) for device in preview_devices)}"

                return self.async_show_form(
                    step_id="batch_configure_result",
                    data_schema=vol.Schema({}),
                    description_placeholders={"result_message": planned_message},
                )

            # Execute batch configuration.
            if self._pending_batch_config is None:
                return self.async_create_entry(data={})

            gateway: DaliGateway = self._pending_batch_config["gateway"]
            params: DeviceParamType = self._pending_batch_config["params"]
            devices = self._pending_batch_config["devices"]
            configured_devices: list[str] = []
            failed_devices: list[str] = []
            items: list[DeviceParamCommand] = [
                DeviceParamCommand(
                    dev_type=device.dev_type,
                    channel=device.channel,
                    address=device.address,
                    param=params,
                )
                for device in devices
            ]

            try:
                gateway.command_set_dev_params(items)
            except DaliGatewayError:
                _LOGGER.exception(
                    "Failed to send batch setDevParam for %d target(s)",
                    len(items),
                )

            # Always attempt to refresh parameters, even if batch command failed.
            # Some devices might have received the command successfully.
            for device in devices:
                try:
                    device.get_device_parameters()
                    configured_devices.append(self._device_label(device))
                except DaliGatewayError:
                    _LOGGER.exception(
                        "Failed to refresh parameters for device %s", device.dev_id
                    )
                    failed_devices.append(self._device_label(device))

            param_summary = "Parameters applied:\n" + self._format_parameter_summary(
                params
            )

            result_message = (
                f"{param_summary}\n\n"
                f"Updated {len(configured_devices)} device(s) with selected parameters."
            )
            if configured_devices:
                result_message += f"\nDevices: {', '.join(configured_devices)}"
            if failed_devices:
                result_message += f"\nFailed: {', '.join(failed_devices)}"

            self._pending_batch_config = None
            self._batch_config_executed = True
            self._batch_config_result_message = result_message

            return self.async_create_entry(data={"result_message": result_message})

        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="batch_configure_result",
            data_schema=vol.Schema({}),
            description_placeholders={
                "result_message": self._batch_config_result_message or ""
            },
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
