# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Dali Center lighting control systems. The integration communicates with Dali Center gateways via MQTT to control DALI lighting devices, groups, and scenes.

## Development Principles

- Use only English in the code, comments, and documentation

## Development Setup

### Virtual Environment

This project uses a virtual environment to manage Python dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Deactivate when done
deactivate
```

### Development Commands

Always run these commands with the virtual environment activated:

#### Type Checking

```bash
mypy --show-error-codes --pretty custom_components/dali_center
```

#### Code Linting

```bash
pylint $(fd .py "custom_components/" "tests")
```

#### Running Tests

```bash
pytest -v
```

## Architecture

### Core Components

#### Integration Setup (`__init__.py`)

- Entry point for the integration
- Manages gateway connection lifecycle using PySrDaliGateway library
- Sets up platforms: Light, Sensor, Button, Event
- Handles device registry and dispatcher signals

#### External Library (PySrDaliGateway)

- **DaliGateway**: Main gateway class handling MQTT communication
- **Device/Group/Scene**: Entity definitions and management
- **Discovery**: Network discovery of Dali Center gateways
- **Helper functions**: Device type detection and utilities

#### Configuration Flow (`config_flow.py`)

- Multi-step configuration wizard
- Gateway discovery and selection
- Entity selection with diff display
- Options flow for refreshing entities

#### Platform Modules

- **Light** (`light.py`): Controls DALI lighting devices and groups
- **Sensor** (`sensor.py`): Energy monitoring and device status
- **Button** (`button.py`): Scene activation buttons
- **Event** (`event.py`): Panel button events (replaces panel sensors)

#### Support Modules

- **Constants** (`const.py`): Domain and configuration constants
- **Types** (`types.py`): TypedDict definitions for Home Assistant integration
- **Helper** (`helper.py`): Utility functions for entity comparison and setup

### Data Flow

1. **Discovery**: Gateway discovery via network scan
2. **Connection**: MQTT connection to selected gateway
3. **Entity Discovery**: Query gateway for devices/groups/scenes
4. **Setup**: Create Home Assistant entities
5. **Runtime**: Handle status updates and commands via MQTT

### MQTT Communication

MQTT communication is handled by the PySrDaliGateway external library:

- **Subscribe Topic**: `/{gw_sn}/client/reciver/`
- **Publish Topic**: `/{gw_sn}/server/publish/`
- **Commands**: `writeDev`, `readDev`, `writeGroup`, `writeScene`
- **Status**: `devStatus`, `onlineStatus`, `reportEnergy`

## Key Files

- `custom_components/dali_center/__init__.py`: Integration setup and lifecycle
- `custom_components/dali_center/config_flow.py`: Configuration UI flows
- `custom_components/dali_center/light.py`: Light platform implementation
- `custom_components/dali_center/sensor.py`: Sensor platform for energy monitoring
- `custom_components/dali_center/button.py`: Button platform for scene activation
- `custom_components/dali_center/event.py`: Event platform for panel button events
- `custom_components/dali_center/const.py`: Domain constants and configuration
- `custom_components/dali_center/types.py`: TypedDict definitions for HA integration
- `custom_components/dali_center/helper.py`: Utility functions
- `custom_components/dali_center/manifest.json`: Integration metadata and dependencies

## Dependencies

- `PySrDaliGateway>=0.1.4`: External library for DALI gateway communication
- Home Assistant core libraries

## Common Development Patterns

### Adding New Device Types

1. Check if device type is supported in PySrDaliGateway library
2. Add entity type definitions in local `types.py` if needed for HA integration
3. Create platform entity class in appropriate platform file (`light.py`, `sensor.py`, etc.)
4. Register platform in `__init__.py` _PLATFORMS list
5. Add entity setup logic in platform's `async_setup_entry` function

### MQTT Message Handling

- MQTT communication is abstracted by PySrDaliGateway library
- Integration subscribes to gateway status updates via dispatcher signals
- Commands sent through PySrDaliGateway's DaliGateway class methods
- Unique device IDs generated from device properties and gateway serial

### Entity Management

- Entities identified by unique_id combining device properties and gateway serial
- Device registry maintains gateway and device information
- Real-time updates handled via Home Assistant's dispatcher system
- Entity state updates triggered by PySrDaliGateway callbacks

## Testing

Tests are located in `tests/` directory and use pytest with asyncio support. Configuration in `pytest.ini` sets up proper test discovery and async handling.

## Development Workflow

### Branch Naming Convention

- **Features**: `feature/description-of-feature`
- **Bug Fixes**: `fix/description-of-fix`
- **Documentation**: `docs/description-of-docs`
- **Refactoring**: `refactor/description-of-refactor`
- **Testing**: `test/description-of-test`

### Commit Message Format

Follow conventional commits format:

```text
type(scope): brief description

Detailed explanation of changes (if necessary)

- Bullet points for multiple changes
- Reference issue numbers (#123)
- Breaking changes noted with BREAKING CHANGE:
```

**Examples:**

- `feat(gateway): add support for DALI device groups`
- `fix(sensor): correct energy sensor precision`
- `docs(readme): update installation instructions`

### Pull Request Process

1. **Create feature branch** from main branch
2. **Create PR** with clear description and test plan
3. **Update documentation** (README.md) if needed
4. **Merge using squash and merge** strategy

### Release Process

1. **Update version** in `manifest.json`
2. **Update CHANGELOG.md** with release notes:
   - Use simplified structure: Added, Fixed, Technical
   - Include issue references (#123) for user-facing changes
   - Include commit hashes (abc1234) for technical changes without issues
   - Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
3. **Commit changes** to main branch
4. **Create and push tag** to upstream: `git tag v{version} && git push upstream v{version}`
5. **Create GitHub release** using `gh release create`
6. **Follow semantic versioning**: MAJOR.MINOR.PATCH

#### Changelog Structure Template

```markdown
## [x.y.z] - YYYY-MM-DD

### Added
- New user-facing features

### Fixed  
- Important bug fixes (#issue)

### Technical
- Dependency updates, CI/CD improvements, code refactoring
```

### Code Quality Requirements

- **Type hints**: All new code must include proper type annotations
- **Error handling**: Use proper exception handling with logging
- **Documentation**: Add docstrings for all public methods and classes
- **Constants**: Define constants in separate constants file
- **Testing**: Write unit tests for all new functionality