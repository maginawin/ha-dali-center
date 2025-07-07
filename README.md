# DALI Center Integration

<!-- [![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE) -->
[![hacs][hacsbadge]][hacs]

The DALI Center integration brings comprehensive DALI lighting control to Home Assistant through DALI Center gateways. Control individual lights, groups, and scenes with real-time status updates and energy monitoring.

<p align="center">
  <img src="docs/img/logo.png" alt="DALI Center Logo" width="200">
</p>

## Features

- **Automatic Gateway Discovery** - Automatically discovers DALI Center gateways on your network
- **Comprehensive Device Control** - Control individual DALI devices, groups, and scenes
- **Energy Monitoring** - Real-time energy consumption tracking for connected devices
- **Scene Management** - One-click scene activation with dedicated button entities
- **Real-time Updates** - Instant status updates via MQTT communication
- **Easy Configuration** - Simple UI-based setup with device selection
- **Multi-Platform Support** - Light, Sensor, and Button entities

## Installation Guide

### Method 1: Manual Installation

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

## Common Issues

- **Issue**: Cannot find gateway devices
  **Solution**: Make sure the gateway is on the same network as Home Assistant and is properly powered and running

- **Issue**: Failed to connect to gateway
  **Solution**: Check if the gateway's MQTT configuration is correct and the gateway is online

- **Issue**: Cannot control devices
  **Solution**: Check if the devices are properly paired with the gateway and the gateway is online

## Development

### Setup Development Environment

```bash
pip install -r requirements.txt
```

### Type Checking

To check the type annotations with MyPy:

```bash
mypy --show-error-codes --pretty custom_components/dali_center
```

### Code Checking

To check the code with Pylint:

```bash
pylint $(fd .py "custom_components/" "tests")
```

### Run Tests

To run the tests:

```bash
pytest -v
```
