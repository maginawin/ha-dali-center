# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-01-07

### Added

- Initial release of DALI Center integration for Home Assistant
- Automatic gateway discovery via network scanning
- Support for DALI lighting devices with brightness and on/off control
- DALI group control for managing multiple devices simultaneously
- Scene activation with dedicated button entities
- Energy monitoring sensors for power consumption tracking
- Motion sensor support for DALI motion detection devices
- Illuminance sensor support for DALI light sensors
- Panel button support for multi-key DALI control panels
- Real-time device status updates via MQTT
- Configuration flow with gateway selection and device discovery
- Entity selection with diff display for easy setup
- Multi-platform support (Light, Sensor, Button entities)
- Comprehensive device registry management
- Gateway offline/online status monitoring

### Technical Features

- MQTT communication with DALI Center gateways
- Device discovery and entity management
- Type-safe TypedDict definitions for all data structures
- Async/await support throughout the codebase
- Proper Home Assistant integration patterns
- Comprehensive test coverage

### Supported Device Types

- DALI Dimmer devices (Type 01xx)
- DALI CCT, RGB, XY, RGBW, RGBWA devices
- DALI Motion sensors (Type 02xx)
- DALI Illuminance sensors
- DALI Control panels (2-Key, 4-Key, 6-Key, 8-Key)
- DALI Groups and Scenes

[Unreleased]: https://github.com/maginawin/ha-dali-center/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/maginawin/ha-dali-center/releases/tag/v0.1.0
