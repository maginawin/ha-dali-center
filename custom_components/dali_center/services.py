"""Service registration and bus scan logic for the Dali Center integration."""

from __future__ import annotations

import contextlib
import logging

from PySrDaliGateway import Device

from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_ADD_ENTITIES, SIGNAL_SCAN_STATE
from .types import DaliCenterConfigEntry

_LOGGER = logging.getLogger(__name__)


def async_setup_services(hass: HomeAssistant) -> None:
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
            await async_do_bus_scan(hass, entry)

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
            await async_do_stop_scan(hass, entry)

    hass.services.async_register(DOMAIN, "scan_bus", async_handle_scan_bus)
    hass.services.async_register(DOMAIN, "stop_scan", async_handle_stop_scan)


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
            return entry
    return None


async def async_do_bus_scan(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> None:
    """Execute bus scan, diff results, and update entities."""
    gateway = entry.runtime_data.gateway
    gw_sn = gateway.gw_sn
    notification_id = f"{DOMAIN}_scan_{gw_sn}"

    # Show "scanning" notification.
    async_create(
        hass,
        "Scanning DALI bus. This may take 5–10 minutes. "
        "Light control may be temporarily unresponsive.",
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
        # Suppress ValueError in case the device was already removed from the list.
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


async def async_do_stop_scan(hass: HomeAssistant, entry: DaliCenterConfigEntry) -> None:
    """Stop an in-progress bus scan."""
    gateway = entry.runtime_data.gateway

    if not gateway.bus_scanning:
        return

    _LOGGER.info("Stopping bus scan for gateway %s", gateway.gw_sn)
    await gateway.stop_scan()

    # Clean up scanning notification.
    notification_id = f"{DOMAIN}_scan_{gateway.gw_sn}"
    async_dismiss(hass, notification_id)
