# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for Dali Center lighting control via MQTT.

- Controls DALI devices, groups, and scenes through Dali Center gateways
- Uses external library: PySrDaliGateway (handles MQTT communication)
- Platforms: Light, Sensor, Button, Event, Switch, Scene

## Architecture

### Core Components

- **Integration Setup** (`__init__.py`): Entry point, gateway lifecycle, platform setup
- **External Library** (PySrDaliGateway): MQTT communication, device/group/scene management, discovery
- **Configuration Flow** (`config_flow.py`): Multi-step wizard, gateway discovery, entity selection
- **Platforms**: Light, Sensor, Button, Event, Switch, Scene
- **Support Modules**: const.py, types.py, helper.py, device_trigger.py

### Data Flow

1. Gateway discovery via network scan
2. MQTT connection to selected gateway
3. Query gateway for devices/groups/scenes
4. Create Home Assistant entities
5. Handle status updates and commands via MQTT

### Key Files

- `__init__.py`: Integration setup and lifecycle
- `config_flow.py`: Configuration UI flows
- `light.py`, `sensor.py`, `button.py`, `event.py`, `switch.py`, `scene.py`: Platform implementations
- `device_trigger.py`: Device trigger support
- `const.py`: Domain constants
- `types.py`: TypedDict definitions
- `helper.py`: Utility functions

## Development Setup

### Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

All development commands must run within activated virtual environment.

### Development Commands

```bash
# Format and lint
ruff format
ruff check --fix

# Type check
mypy --show-error-codes --pretty {project_path}
```

## Code Quality Guidelines

Follow Home Assistant's [Style Guidelines](https://developers.home-assistant.io/docs/development_guidelines/). Use Context7 MCP to query detailed documentation when needed.

### Key Rules

- **Logging**: Use percentage formatting, not f-strings (`"Gateway %s connected"` not `f"Gateway {gw} connected"`)
- **Comments**: Full sentences with periods. Comment non-obvious decisions, not obvious code
- **Entity Attributes**: Use `_attr_*` pattern in `__init__`, avoid `@property` decorators
- **Type Hints**: Required for all new code
- **Error Handling**: Proper exception handling with appropriate logging

### Resources

- [Home Assistant Development Guidelines](https://developers.home-assistant.io/docs/development_guidelines/)
- [Home Assistant Entity Architecture](https://developers.home-assistant.io/docs/core/entity/)
- Use Context7 to query Home Assistant documentation for specific patterns

## Development Principles

- **Code Language**: Use English in code, comments, and documentation files
- **Communication Language**: When communicating with the user/developer, use **Chinese (中文)** as the primary language
- **Incremental Development**: Propose each code change and get user approval before implementing. Present plan first, then modify one section at a time.
- Code readability first: prefer self-documenting code over comments
- Document design decisions and rationale for significant changes
