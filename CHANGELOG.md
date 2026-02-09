# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.0] - 2026-02-09

### Added

- DALI bus scan with dynamic entity management (#71)

### Fixed

- Handle scan cancellation and always send stop command (#72)
- Add estimated scan duration to notification

### Changed

- Simplify code and reduce duplication (#70)
- Apply HA best practices to all platforms (#68)

### Documentation

- Add minimum gateway version requirements

## [0.11.5] - 2025-12-16

### Changed

- Bump PySrDaliGateway dependency to >=0.19.3
  - Inbound callback batching for improved performance
  - Client ID timestamp to prevent duplicate reconnections
  - Reduced verbose debug logging

### Technical

- Applied base entity classes to reduce code duplication
- Removed auto-trigger claude review workflow

## [0.11.4] - 2025-12-12

### Fixed

- Thread-safety issue in PySrDaliGateway causing Signal 11 (SIGSEGV) crashes with multiple gateways (#63)

## [0.11.3] - 2025-12-11

### Fixed

- Thundering herd problem causing Signal 11 crashes when multiple gateways initialize simultaneously (#66)

## [0.11.2] - 2025-12-10

### Fixed

- Race condition in event.py causing segfault during startup when multiple integrations load concurrently (#65)

## [0.11.1] - 2025-12-08

### Added

- MAC address connection and unique ID validation for improved device identification (#62)

### Fixed

- Thread-safe callback handling and auto-reconnection support for gateway stability (#64)

## [0.11.0] - 2025-12-05

### Added

- DHCP discovery support for automatic gateway IP address updates (#61)

### Technical

- Introduced base entity class to optimize API calls and reduce code duplication (#60)
- Removed manual state updates in light groups and all-lights entities (#60)

## [0.10.0] - 2025-11-27

### Added

- Device parameter configuration for lights (fade rate, fade time) directly from device cards (#53, #59)
- Batch device configuration updates via controller card (#53, #59)
- Identify button for devices to locate physical lights (#58)

### Technical

- Added Claude Code GitHub Workflow for automated testing (#57)

## [0.9.4] - 2025-11-20

### Technical

- **BREAKING CHANGE**: Updated PySrDaliGateway dependency to >=0.16.2 with incompatible API changes (#54)
- Simplified callback handler implementation by moving dev_id filtering to SDK (7e26faf)

## [0.9.3] - 2025-11-05

### Technical

- Gateway setup performance optimizations (#52)
- Documentation improvements for project instructions (f50f112, 7114d35)

## [0.9.2] - 2025-10-28

### Fixed

- clean stale devices/entities on options refresh (#51)

## [0.9.1] - 2025-10-27

### Fixed

- Manual device synchronization option in configuration flow (#50)
- Panel event entity availability and functionality (#50)

## [0.9.0] - 2025-10-24

### Added

- Automatic device, group, and scene synchronization during setup; manual selection removed from the config flow (#47)

### Fixed

- Entities now register gateway callbacks directly so availability, energy, and sensor updates reach Home Assistant immediately (#48)

### Technical

- **BREAKING CHANGE**: Existing gateways migrate to the new credential schema; remove and re-add the integration only if migration fails (#47)
- Bumped PySrDaliGateway dependency to >=0.15.0 (#48)
- Updated integration metadata to declare Dali Center as a Home Assistant hub (364359c)

## [0.8.0] - 2025-09-19

### Added

- Native Home Assistant scene platform support (#45)
- Device state tracking in scene attributes
- Support for group devices in scene configurations

### Fixed

- Scene entity mapping and activation
- Group device unique ID generation in scenes

### Technical

- **BREAKING CHANGE**: Scenes migrated from button entities to native scene platform - users need to manually refresh scenes in integration options
- Removed scene functionality from button platform (773a7d5, 5ec93e5, efa3417)
- Updated documentation with Home Assistant version compatibility requirements (007263b)

## [0.7.1] - 2025-09-18

### Fixed

- MQTT compatibility with PySrDaliGateway 0.11.1 update (#43)

### Technical

- Standardized entity attributes and gateway handling across all entity types (#44)
- Improved consistency of entity initialization and attribute structure (9598f29)
- Bug report gateway version fields for improved debugging (1c7b660)

## [0.7.0] - 2025-09-11

### Added

- Enhanced light group functionality with real-time state synchronization (#39, #38)
- Gateway restart button for easy gateway management (#36)
- Device tracking capabilities for light groups (#38)

### Fixed

- Centralized gateway availability handling for improved reliability (#34)
- Broadcast color calculations in DaliCenterAllLights using Device API (#37)

### Technical

- **BREAKING CHANGE**: Enhanced light group functionality requires users to refresh group and device lists via Options flow
- Modernized Home Assistant API and dependencies (#35)

## [0.6.0] - 2025-08-28

### Added

- All Lights control entity for gateway broadcast functionality (#32)

### Fixed

- Scene state sync issues with optimistic brightness updates (3e111ef)
- Entity refresh process handling for gateway connection stability (#29)

### Technical

- Code formatting improvements with ruff format (#24)
- Enhanced type checking with full time support for pylance (#23)

## [0.5.1] - 2025-08-16

### Technical

- Updated button event naming convention for consistency: `single_click` → `press`, `double_click` → `double_press`, `long_press` → `hold`, `long_press_stop` → `release` (#22)
- Updated all translation files and panel configurations to use new event names (#22)
- Updated PySrDaliGateway dependency to v0.6.0 (6eac361)

## [0.5.0] - 2025-08-15

### Added

- Enhanced Event entities with native device trigger support for panel buttons (#21)
- Device trigger integration for improved automation workflow (#21)

### Fixed

- Simplified automation creation process by replacing inconsistent Button entities (#21)

### Technical

- **BREAKING CHANGE**: Removed Panel Button entities in favor of Event entities with device triggers (#21)
- Users need to refresh entities via Options flow to get new Event entities
- Updated PySrDaliGateway dependency to v0.5.1 for enhanced event handling

## [0.4.0] - 2025-08-06

### Added

- Gateway IP refresh option in configuration flow to handle DHCP IP changes (#20)

### Technical  

- Modularized configuration flow with helper classes for better code organization (#19)
- Updated test cases for button event sensor switch platform (#18)

## [0.3.0] - 2025-07-30

### Added

- Support for multiple motion sensor types (1 to 20) with updated detection logic (#15)
- Pairing guide in configuration flow for better user experience (#14)

### Technical

- Updated PySrDaliGateway dependency to v0.4.0 for improved functionality (ee45e56)
- Established comprehensive test framework with pytest and coverage reporting (#17, #16)
- Enhanced CI/CD pipeline with Codecov integration for code coverage tracking (b123c9c)
- Updated release workflow documentation in development guide (a43ee90)

## [0.2.0] - 2025-07-23

### Added

- Switch platform for Illuminance sensor device enable/disable control (#11)
- MQTTS (MQTT over TLS) connection support, whether it is enabled depends on the gateway’s configuration. (#9)
- Enhanced gateway information display (#10)

### Fixed

- Improved error handling and logging throughout the integration (#12, #13)
- Enhanced error notification system (#12)

### Technical

- Updated PySrDaliGateway dependency to v0.3.0 for improved functionality (54a9e24)
- Enhanced bug report template with detailed log instructions (a81c45c)

## [0.1.2] - 2025-07-15

### Added

- Automated release workflow for streamlined version management (8300c73)
- Enhanced bug report forms with improved log instructions (234a2d7, c7b5394)

### Changed

- Updated PySrDaliGateway dependency to version 0.1.4 for improved compatibility (6448845)
- Simplified event handling logic for better performance (6448845)
- Simplified bug report form by removing description field (a2f403b)

### Fixed

- Code scanning security alert regarding workflow permissions (#5)

### Infrastructure

- Added comprehensive CI/CD pipeline with automated release management
- Enhanced issue templates for better bug reporting experience

## [0.1.1] - 2025-07-10

### Added

- HACS integration support for one-click installation
- CodeQL code quality analysis workflow
- Comprehensive entity handling improvements

### Changed

- **BREAKING**: Migrated panel sensors to event entities for improved handling
- Updated to PySrDaliGateway library v0.1.3 (replacing internal DALI Gateway)
- Refactored import structure for better maintainability
- Updated installation guide with HACS one-click integration instructions
- Improved DALI Center logo using Home Assistant brand assets

### Fixed

- Panel sensor handling now uses proper event entities
- Default brightness and RGBW color values for light entities
- Type checking issues (mypy/pylint) resolved
- Hassfest validation issues fixed

### Removed

- Removed unused dependencies and cleaned up requirements structure
- Replaced internal DALI Gateway implementation with external library

## [0.1.0] - 2025-07-07

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

[Unreleased]: https://github.com/maginawin/ha-dali-center/compare/v0.11.5...HEAD
[0.11.5]: https://github.com/maginawin/ha-dali-center/compare/v0.11.4...v0.11.5
[0.11.4]: https://github.com/maginawin/ha-dali-center/compare/v0.11.3...v0.11.4
[0.11.3]: https://github.com/maginawin/ha-dali-center/compare/v0.11.2...v0.11.3
[0.11.2]: https://github.com/maginawin/ha-dali-center/compare/v0.11.1...v0.11.2
[0.11.1]: https://github.com/maginawin/ha-dali-center/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/maginawin/ha-dali-center/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/maginawin/ha-dali-center/compare/v0.9.4...v0.10.0
[0.9.4]: https://github.com/maginawin/ha-dali-center/compare/v0.9.3...v0.9.4
[0.9.3]: https://github.com/maginawin/ha-dali-center/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/maginawin/ha-dali-center/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/maginawin/ha-dali-center/compare/v0.9.0...v0.9.1
[0.9.0]: https://github.com/maginawin/ha-dali-center/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/maginawin/ha-dali-center/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/maginawin/ha-dali-center/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/maginawin/ha-dali-center/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/maginawin/ha-dali-center/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/maginawin/ha-dali-center/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/maginawin/ha-dali-center/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/maginawin/ha-dali-center/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/maginawin/ha-dali-center/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/maginawin/ha-dali-center/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/maginawin/ha-dali-center/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/maginawin/ha-dali-center/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/maginawin/ha-dali-center/releases/tag/v0.1.0
