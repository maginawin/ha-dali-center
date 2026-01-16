# DALI Center Integration

![GitHub Release][releases-shield]
![GitHub Activity][commits-shield]
![hacs][hacsbadge]

[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/m/maginawin/ha-dali-center.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/maginawin/ha-dali-center.svg?style=for-the-badge

The DALI Center integration brings comprehensive DALI lighting control to Home Assistant through DALI Center gateways. Control individual lights, groups, and scenes with real-time status updates and energy monitoring.

<p align="center">
  <img src="https://brands.home-assistant.io/dali_center/logo@2x.png" alt="DALI Center Logo" width="500">
</p>

## System Requirements

- **Home Assistant**: Version 2024.4.4 or later
- **Python**: Version 3.11 or later (as required by Home Assistant)

## Hardware Requirements

⚠️ **Important**: This integration requires a **Sunricher DALI Center Gateway** to function. It is NOT compatible with DALI gateways from different manufacturers.

**Supported Gateway:**

- [DIN Rail Ethernet (IP) DALI Gateway SR-GW-EDA](https://www.sunricher.com/din-rail-ethernet-dali-gateway-sr-gw-eda.html)

**Minimum Gateway Versions:**

- Software Version: 3.59 or later
- Firmware Version: 1.45 or later

**Supported DALI Devices:**

### Lighting Drivers

- DALI DT6 Dimmable Driver
- DALI DT8 Tc Dimmable Driver  
- DALI DT8 RGB Dimmable Driver
- DALI DT8 XY Dimmable Driver
- DALI DT8 RGBW Dimmable Driver
- DALI DT8 RGBWA Dimmable Driver

### Sensors

- DALI-2 Motion Sensor
- DALI-2 Illuminance Sensor

### Control Panels

- DALI-2 2-Key Push Button Panel
- DALI-2 4-Key Push Button Panel
- DALI-2 6-Key Push Button Panel
- DALI-2 8-Key Push Button Panel

## Features

- **Automatic Gateway Discovery** - Automatically discovers DALI Center gateways on your network
- **Comprehensive Device Control** - Control individual DALI devices, groups, and scenes
- **Energy Monitoring** - Real-time energy consumption tracking for connected devices
- **Scene Management** - One-click scene activation with dedicated button entities
- **Real-time Updates** - Instant status updates via MQTT communication
- **Easy Configuration** - Simple UI-based setup with device selection
- **Multi-Platform Support** - Light, Sensor, and Button entities

## Installation Guide

### Method 1: [HACS](https://hacs.xyz/) (Recommended)

One-click installation from HACS:

[![Open your Home Assistant instance and open the DALI Center integration inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=maginawin&repository=ha-dali-center&category=integration)

### Method 2: Manual Installation

1. Download the ZIP file of this repository or clone it

   ```bash
   git clone https://github.com/maginawin/ha-dali-center.git
   ```

2. Create the custom components directory (if it doesn't exist)

   ```bash
   mkdir -p /config/custom_components/
   ```

3. Copy the integration files to Home Assistant config directory

   ```bash
   cp -r ha-dali-center/custom_components/dali_center /config/custom_components/
   ```

4. Restart Home Assistant

   ```bash
   ha core restart
   ```

## Configuration Steps

1. In Home Assistant frontend, navigate to **Settings → Devices & Services → Add Integration**
2. Search for "Dali Center" and select it
3. The integration will automatically search for Dali Center gateways on your network
4. Select the gateway you want to connect to
5. The integration will search for devices connected to the gateway
6. Select the devices you want to add and confirm integration creation

## Update Steps

To update the integration, repeat the installation steps to overwrite the existing files, then restart Home Assistant.

## Uninstallation Method

1. In Home Assistant frontend, navigate to **Settings → Devices & Services**
2. Find the "Dali Center" integration card
3. Click the menu button (three dots), then select "Delete"
4. Confirm the deletion

To completely remove the integration files:

```bash
rm -rf /config/custom_components/dali_center
```

## Available Entities

### Light Entities

- `light.DEVICE_NAME` - Individual DALI lighting devices with brightness and on/off control
- `light.GROUP_NAME` - DALI group entities for controlling multiple devices simultaneously

### Sensor Entities

- `sensor.DEVICE_NAME_current_hour_energy` - Energy consumption tracking for individual devices
- `sensor.DEVICE_NAME_state` - Motion sensor state (motion/illuminance sensors)
- `sensor.DEVICE_NAME_event` - Panel button press events

### Button Entities

- `button.SCENE_NAME` - Scene activation buttons for instant lighting presets
- `button.DEVICE_NAME_button_N` - Individual panel button controls (for multi-key panels)

## Support and Bug Reporting

If you encounter issues with this integration, please:

1. **Check existing issues** in the [GitHub Issues](https://github.com/maginawin/ha-dali-center/issues) section
2. **Create a new bug report** using our [bug report template](https://github.com/maginawin/ha-dali-center/issues/new?assignees=&labels=bug&template=bug_report.yml&title=%5BBug%5D%3A+) if your issue isn't already reported
