# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Dali Center lighting control systems. The integration communicates with Dali Center gateways via MQTT to control DALI lighting devices, groups, and scenes.

## Development Principles

- Use only English in the code, comments, and documentation
- **Mentorship-Driven Development**: All AI interactions should enhance developer skills
- **Architecture-First Thinking**: Design decisions before implementation details
- **Learning Documentation**: Capture decision rationale and alternatives considered
- **Code Readability First**: Minimize comments in favor of self-documenting code
- **Virtual Environment Requirement**: All development commands must be executed within the activated virtual environment

## Code Quality Guidelines

Following Home Assistant's [Style Guidelines](https://developers.home-assistant.io/docs/development_guidelines/) for integration development.

### Logging Best Practices

**Source**: [Home Assistant Style Guidelines - Logging](https://developers.home-assistant.io/docs/development_guidelines/)

#### Logging Format

Always use percentage formatting (not f-strings) for log messages:

```python
# Correct
_LOGGER.info("Gateway %s connected with %d devices", gw_sn, device_count)

# Incorrect
_LOGGER.info(f"Gateway {gw_sn} connected with {device_count} devices")
```

**Reason**: Percentage formatting avoids formatting the message when logging is suppressed at that level, improving performance.

#### Log Level Usage

- **Exception**: Use `_LOGGER.exception()` in exception handlers to include stack trace
- **Error**: Critical failures requiring user attention
- **Warning**: Recoverable issues or deprecated features (not normal operations)
- **Info**: Important state transitions and milestones (use sparingly)
- **Debug**: Detailed diagnostic information for troubleshooting

#### What NOT to Log

- Redundant logs that repeat what code obviously does
- Success confirmations for normal operations (absence of error = success)
- Verbose parameter dumps (Home Assistant traces capture this)
- Low-value debug messages that don't aid diagnostics

### Comment Guidelines

**Source**: [Home Assistant Style Guidelines - Comments](https://developers.home-assistant.io/docs/development_guidelines/)

Comments should be full sentences ending with a period.

#### When to Comment

- Non-obvious design decisions
- Complex algorithms requiring explanation
- Important warnings or gotchas
- Workarounds with context

#### Prefer Self-Documenting Code

Instead of comments, use:

- Clear, descriptive variable and function names
- Type hints and docstrings (Google style)
- Small, well-named functions
- Logical code organization

### Entity Class Best Practices

**Source**: Home Assistant entity architecture patterns

#### Attribute Declaration Pattern

Distinguish between constant class-level attributes and dynamic instance-level state:

**Class-level attributes** (constants shared across all instances):

```python
class MyEntity(BaseEntity):
    _attr_has_entity_name = True
    _attr_name = "Sensor"  # Same for all instances
    _attr_icon = "mdi:thermometer"  # Same for all instances
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_min_value = 1000  # Constant
    _attr_max_value = 8000  # Constant
```

**Instance-level attributes** (unique per instance):

```python
    def __init__(self, device: Device) -> None:
        super().__init__()
        self._device = device
        self._attr_unique_id = f"{device.id}_temperature"  # Dynamic
        self._attr_native_value = device.current_temp  # State
        self._attr_available = device.status == "online"  # State
        self._attr_device_info = {  # Device info set in constructor
            "identifiers": {(DOMAIN, device.dev_id)},
            "name": device.name,
            "manufacturer": MANUFACTURER,
            "model": device.model,
            "via_device": (DOMAIN, device.gw_sn),
        }
```

#### Attribute Declaration Guidelines

**Always use `_attr_*` pattern in constructors. Avoid `@property` and `@cached_property` decorators.**

All entity attributes should be set in the constructor using the `_attr_*` naming convention:

**Good - Attributes in constructor:**

```python
def __init__(self, device: Device) -> None:
    super().__init__()
    self._attr_unique_id = device.unique_id
    self._attr_device_info = {
        "identifiers": {(DOMAIN, device.dev_id)},
        "name": device.name,
        "manufacturer": MANUFACTURER,
        "model": device.model,
        "via_device": (DOMAIN, device.gw_sn),
    }
    self._attr_extra_state_attributes = {
        "gateway_sn": device.gw_sn,
        "address": device.address,
        "channel": device.channel,
    }
```

**Bad - Using property decorators:**

```python
@cached_property
def device_info(self) -> DeviceInfo:
    return {"identifiers": {(DOMAIN, self._device.dev_id)}}

@cached_property
def extra_state_attributes(self) -> dict[str, Any]:
    return {"address": self._device.address}
```

For dynamic data that needs updating, use methods to update `_attr_*` attributes:

```python
async def _async_update_group_devices(self) -> None:
    # ... fetch data
    self._attr_extra_state_attributes.update({
        "entity_id": self._group_entity_ids,
        "total_devices": len(devices),
    })
```

#### Benefits

- **Performance**: Class-level attributes shared across instances, reducing memory
- **Clarity**: Clear separation between configuration (class) and state (instance)
- **Consistency**: Uniform pattern across all entity classes
- **Maintainability**: Easier to identify what changes vs what's constant

### Code Pattern Best Practices

#### Use Dictionary Mapping Instead of If-Elif Chains

When mapping string values to other values, prefer dictionaries over if-elif chains for clarity and maintainability.

**Bad - If-Elif Chain:**

```python
def map_color_mode(self, mode: str) -> ColorMode:
    if mode == "color_temp":
        return ColorMode.COLOR_TEMP
    elif mode == "hs":
        return ColorMode.HS
    elif mode == "rgbw":
        return ColorMode.RGBW
    else:
        return ColorMode.BRIGHTNESS
```

**Good - Dictionary Mapping:**

```python
def map_color_mode(self, mode: str) -> ColorMode:
    color_mode_mapping: dict[str, ColorMode] = {
        "color_temp": ColorMode.COLOR_TEMP,
        "hs": ColorMode.HS,
        "rgbw": ColorMode.RGBW,
    }
    return color_mode_mapping.get(mode, ColorMode.BRIGHTNESS)
```

**Benefits:**

- **Readability**: Mapping is immediately visible as a data structure
- **Maintainability**: Adding new mappings requires only one line
- **Performance**: O(1) dictionary lookup vs O(n) if-elif chain
- **Extensibility**: Easy to move mapping to class/module level if needed

**When NOT to use dictionaries:**

- Complex conditional logic beyond simple value mapping
- Binary decisions (single if-else)
- Different function signatures for each case

### References

- [Home Assistant Development Guidelines](https://developers.home-assistant.io/docs/development_guidelines/)
- [Home Assistant Core - Best Practices](https://developers.home-assistant.io/docs/development_checklist/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Python @cached_property](https://docs.python.org/3/library/functools.html#functools.cached_property)

## Development Setup

### Virtual Environment

This project uses a virtual environment to manage Python dependencies:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install project with development dependencies
pip install -e ".[dev]"

# Deactivate when done
deactivate
```

### Development Commands

Always run these commands with the virtual environment activated:

#### Code Formatting and Linting

```bash
# Format code with ruff
ruff format

# Run linting checks with ruff
ruff check

# Fix auto-fixable linting issues
ruff check --fix
```

#### Type Checking

```bash
mypy --show-error-codes --pretty custom_components/dali_center
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

Follow conventional commits format with emphasis on brevity and clarity:

```text
type(scope): concise summary of what changed

Optional body for context (why, not what)
```

**Commit Types:**

- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring without behavior change
- `docs`: Documentation changes
- `test`: Test additions or modifications
- `chore`: Maintenance tasks (dependencies, tooling, releases)

**Best Practices:**

- **Keep subject line under 72 characters**
- **Use imperative mood**: "add feature" not "added feature" or "adds feature"
- **Be specific but concise**: Focus on the impact, not implementation details
- **Omit obvious details**: The diff shows the "what", commit explains the "why"
- **Group related changes**: Use single commit for cohesive changes across files

**Examples:**

✅ Good:

- `feat(gateway): add group control support`
- `fix(sensor): correct energy calculation overflow`
- `refactor: remove redundant logs and comments`
- `chore(release): bump version to 0.2.0`

❌ Too verbose:

- `refactor: remove unnecessary logs and comments for code clarity. Remove verbose debug logs that echo parameters. Remove obvious comments...`

❌ Too vague:

- `refactor: cleanup`
- `fix: bug fixes`

**IMPORTANT**: Do not include Claude Code signatures, co-author attributions, or AI-generated markers in commit messages. Keep commits clean and focused on the technical changes.

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
   - Update version links at bottom of changelog
3. **Commit changes** to main branch using format: `chore(release): bump version to x.y.z`
4. **Create and push tag** to upstream: `git tag v{version} && git push upstream v{version}`
5. **Create GitHub release** using `gh release create v{version} --title "v{version}" --notes "..."`
   - Copy release notes from CHANGELOG.md with same structure (Added, Fixed, Technical sections)
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
- **Architecture Documentation**: Document significant design decisions and alternatives considered
