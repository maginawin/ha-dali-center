"""The Dali Center integration."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import async_timeout
from PySrDaliGateway import DaliGateway, Device
from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_GATEWAY_LEGACY,
    CONF_SERIAL_NUMBER,
    DOMAIN,
    MANUFACTURER,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_SCAN_STATE,
    sn_to_mac,
)
from .helper import migrate_gateway_config
from .types import DaliCenterConfigEntry, DaliCenterData

_PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.SWITCH,
    Platform.SCENE,
    Platform.NUMBER,
]
_LOGGER = logging.getLogger(__name__)

# Semaphore for limiting concurrent gateway initialization.
# This prevents the "thundering herd" problem when multiple gateways are
# configured. Without limiting concurrency, all gateways connecting simultaneously
# can cause Signal 11 crashes due to event loop overload.
# Allow 2 concurrent initializations as a balance between safety and startup time.
# See: https://github.com/maginawin/ha-dali-center/issues/63
_SETUP_SEMAPHORE = asyncio.Semaphore(2)


def _setup_dependency_logging() -> None:
    current_logger = logging.getLogger(__name__)
    current_level = current_logger.getEffectiveLevel()

    gateway_logger = logging.getLogger("PySrDaliGateway")
    gateway_logger.setLevel(current_level)


async def _notify_user_error(
    hass: HomeAssistant, title: str, message: str, gw_sn: str = ""
) -> None:
    notification_id = f"dali_center_{gw_sn}_{hash(title + message)}"
    gw_part = f" ({gw_sn})" if gw_sn else ""
    full_title = f"DALI Center{gw_part}: {title}"

    async_create(
        hass,
        message,
        title=full_title,
        notification_id=notification_id,
    )


async def async_migrate_entry(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> bool:
    """Migrate old entry format to new format."""
    if entry.version == 1:
        old_data = dict(entry.data)

        if CONF_GATEWAY_LEGACY in old_data:
            _LOGGER.info("Migrating gateway configuration from legacy format")
            new_data = migrate_gateway_config(old_data)

            _ = hass.config_entries.async_update_entry(
                entry,
                data=new_data,
                version=2,
            )
            _LOGGER.info("Migration to version 2 completed successfully")
        else:
            _ = hass.config_entries.async_update_entry(entry, version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Set up dali_center from a config entry using paho-mqtt."""
    _setup_dependency_logging()

    gateway = DaliGateway(
        gw_sn=entry.data[CONF_SERIAL_NUMBER],
        gw_ip=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        passwd=entry.data[CONF_PASSWORD],
        name=entry.data[CONF_NAME],
        loop=hass.loop,  # Thread-safe callback dispatch
    )

    # Serialize gateway connection and discovery to prevent thundering herd.
    # This avoids Signal 11 crashes when multiple gateways initialize concurrently.
    _LOGGER.debug("Gateway %s: Waiting for setup semaphore", gateway.gw_sn)
    async with _SETUP_SEMAPHORE:
        _LOGGER.debug("Gateway %s: Acquired setup semaphore", gateway.gw_sn)

        # Reduce timeout from 60s to 15s for local devices
        try:
            async with async_timeout.timeout(15):
                await gateway.connect()
        except DaliGatewayError as exc:
            # Use warning level to reduce log noise for expected connection failures.
            _LOGGER.warning("Error connecting to gateway %s: %s", gateway.gw_sn, exc)
            await _notify_user_error(hass, "Connection Failed", str(exc), gateway.gw_sn)
            raise ConfigEntryNotReady(
                f"Gateway {gateway.gw_sn} connection failed: {exc}"
            ) from exc
        except TimeoutError as exc:
            _LOGGER.warning("Timeout connecting to gateway %s", gateway.gw_sn)
            await _notify_user_error(
                hass,
                "Connection Timeout",
                f"Timeout while connecting to DALI Center gateway. {exc}",
                gateway.gw_sn,
            )
            raise ConfigEntryNotReady(
                f"Gateway {gateway.gw_sn} connection timeout"
            ) from exc

        try:
            devices, groups, scenes = await asyncio.gather(
                gateway.discover_devices(),
                gateway.discover_groups(),
                gateway.discover_scenes(),
            )
        except DaliGatewayError as exc:
            _LOGGER.warning(
                "Error discovering entities for gateway %s: %s", gateway.gw_sn, exc
            )
            await _notify_user_error(hass, "Discovery Failed", str(exc), gateway.gw_sn)
            await gateway.disconnect()
            raise ConfigEntryNotReady(
                f"Failed to discover entities for gateway {gateway.gw_sn}: {exc}"
            ) from exc

        _LOGGER.debug("Gateway %s: Releasing setup semaphore", gateway.gw_sn)

    entry.runtime_data = DaliCenterData(
        gateway=gateway,
        devices=devices,
        groups=groups,
        scenes=scenes,
    )

    dev_reg = dr.async_get(hass)
    _ = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, gateway.gw_sn)},
        connections={(CONNECTION_NETWORK_MAC, sn_to_mac(gateway.gw_sn))},
        manufacturer=MANUFACTURER,
        name=gateway.name,
        model="SR-GW-EDA",
        serial_number=gateway.gw_sn,
        sw_version=gateway.software_version or None,
        hw_version=gateway.firmware_version or None,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    # Register services once (guard against duplicate registration from multiple entries).
    if not hass.services.has_service(DOMAIN, "scan_bus"):
        _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> bool:
    """Unload a config entry."""
    gateway = entry.runtime_data.gateway
    _LOGGER.info("Disconnecting from gateway %s", gateway.gw_sn)

    try:
        await gateway.disconnect()
    except DaliGatewayError as exc:
        _LOGGER.exception("Error disconnecting from gateway %s", gateway.gw_sn)
        await _notify_user_error(hass, "Disconnection Failed", str(exc), gateway.gw_sn)

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


def _resolve_entry_from_device_id(
    hass: HomeAssistant, device_id: str
) -> DaliCenterConfigEntry | None:
    """Resolve a device_id to its DaliCenterConfigEntry."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if device is None:
        return None
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN:
            return entry  # type: ignore[return-value]
    return None


def _register_services(hass: HomeAssistant) -> None:
    """Register scan_bus and stop_scan services."""

    async def async_handle_scan_bus(call: ServiceCall) -> None:
        """Handle the scan_bus service call."""
        device_ids: list[str] = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry = _resolve_entry_from_device_id(hass, device_id)
            if entry is None:
                _LOGGER.warning("No config entry found for device %s", device_id)
                continue
            await _async_do_bus_scan(hass, entry)

    async def async_handle_stop_scan(call: ServiceCall) -> None:
        """Handle the stop_scan service call."""
        device_ids: list[str] = call.data.get("device_id", [])
        if isinstance(device_ids, str):
            device_ids = [device_ids]
        for device_id in device_ids:
            entry = _resolve_entry_from_device_id(hass, device_id)
            if entry is None:
                _LOGGER.warning("No config entry found for device %s", device_id)
                continue
            await _async_do_stop_scan(hass, entry)

    hass.services.async_register(DOMAIN, "scan_bus", async_handle_scan_bus)
    hass.services.async_register(DOMAIN, "stop_scan", async_handle_stop_scan)


async def _async_do_bus_scan(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> None:
    """Execute bus scan, diff results, and update entities."""
    gateway = entry.runtime_data.gateway
    gw_sn = gateway.gw_sn
    notification_id = f"{DOMAIN}_scan_{gw_sn}"

    # Show "scanning" notification.
    async_create(
        hass,
        "Scanning DALI bus. Light control may be temporarily unresponsive.",
        title=f"DALI Center ({gw_sn}): Bus Scan",
        notification_id=notification_id,
    )

    # Notify buttons that scanning started.
    async_dispatcher_send(hass, f"{SIGNAL_SCAN_STATE}_{entry.entry_id}", True)

    try:
        scan_result = await gateway.scan_bus(gateway.channel_total)
    except TimeoutError:
        _LOGGER.warning("Bus scan timed out for gateway %s", gw_sn)
        async_create(
            hass,
            "Bus scan timed out after 600 seconds. No changes were made.",
            title=f"DALI Center ({gw_sn}): Bus Scan Failed",
            notification_id=notification_id,
        )
        return
    except Exception:
        _LOGGER.exception("Bus scan failed for gateway %s", gw_sn)
        async_dismiss(hass, notification_id)
        return
    finally:
        # Notify buttons that scanning stopped.
        async_dispatcher_send(hass, f"{SIGNAL_SCAN_STATE}_{entry.entry_id}", False)

    # Diff scan results against current device list.
    existing_devices = entry.runtime_data.devices
    scanned_ids = {dev.dev_id for dev in scan_result}
    existing_ids = {dev.dev_id for dev in existing_devices}

    new_device_ids = scanned_ids - existing_ids
    removed_device_ids = existing_ids - scanned_ids

    new_devices = [dev for dev in scan_result if dev.dev_id in new_device_ids]
    removed_devices = [
        dev for dev in existing_devices if dev.dev_id in removed_device_ids
    ]

    # Handle new devices: extend in-place, then dispatch to platforms.
    if new_devices:
        existing_devices.extend(new_devices)
        _LOGGER.info("Gateway %s: %d new device(s) discovered", gw_sn, len(new_devices))
        async_dispatcher_send(
            hass, f"{SIGNAL_ADD_ENTITIES}_{entry.entry_id}", new_devices
        )

    # Handle removed devices: remove in-place, then remove from device registry.
    if removed_devices:
        _remove_devices(hass, entry, removed_devices)

    # Show result notification.
    async_create(
        hass,
        f"Scan complete: {len(new_devices)} added, {len(removed_devices)} removed, "
        f"{len(scanned_ids) - len(new_device_ids)} unchanged.",
        title=f"DALI Center ({gw_sn}): Bus Scan Complete",
        notification_id=notification_id,
    )


def _remove_devices(
    hass: HomeAssistant,
    entry: DaliCenterConfigEntry,
    removed_devices: list[Device],
) -> None:
    """Remove devices from runtime_data and device registry."""
    dev_reg = dr.async_get(hass)
    existing_devices = entry.runtime_data.devices
    gw_sn = entry.runtime_data.gateway.gw_sn

    for dev in removed_devices:
        # Remove from runtime_data in-place.
        with contextlib.suppress(ValueError):
            existing_devices.remove(dev)

        # Remove from HA device registry (cascades to entities).
        device_entry = dev_reg.async_get_device(identifiers={(DOMAIN, dev.dev_id)})
        if device_entry:
            dev_reg.async_remove_device(device_entry.id)
            _LOGGER.info(
                "Gateway %s: Removed device %s (%s)",
                gw_sn,
                dev.name,
                dev.dev_id,
            )


async def _async_do_stop_scan(
    hass: HomeAssistant, entry: DaliCenterConfigEntry
) -> None:
    """Stop an in-progress bus scan."""
    gateway = entry.runtime_data.gateway

    if not gateway.bus_scanning:
        return

    _LOGGER.info("Stopping bus scan for gateway %s", gateway.gw_sn)
    await gateway.stop_scan()

    # Clean up scanning notification.
    notification_id = f"{DOMAIN}_scan_{gateway.gw_sn}"
    async_dismiss(hass, notification_id)
