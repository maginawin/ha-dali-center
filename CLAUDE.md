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
mypy --show-error-codes --pretty custom_components/dali_center
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

- Use English in code, comments, and documentation
- Code readability first: prefer self-documenting code over comments
- Document design decisions and rationale for significant changes

## Development Workflow

### Branch Naming Convention

- **Features**: `feature/description-of-feature`
- **Bug Fixes**: `fix/description-of-fix`
- **Documentation**: `docs/description-of-docs`
- **Refactoring**: `refactor/description-of-refactor`
- **Testing**: `test/description-of-test`

### Commit Message Format

Follow conventional commits format with **strong emphasis on brevity and clarity**:

```text
type(scope): concise summary of what changed

- Optional bullet point for key changes
- Keep each point short and focused
- Maximum 3-4 bullet points
```

**Commit Types:**

- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code restructuring without behavior change
- `docs`: Documentation changes
- `test`: Test additions or modifications
- `chore`: Maintenance tasks (dependencies, tooling, releases)

**Key Principles: Be specific, concise, and focus on impact over details.**

- Keep subject line under 72 characters
- Use imperative mood: "add feature" not "added feature"
- Omit obvious details: diff shows "what", commit explains "why"
- Use 3-4 bullet points maximum if body is needed

**IMPORTANT: No Claude Code signatures, co-author attributions, or AI-generated markers in commit messages.**

**Examples:**

```text
# Good
feat(gateway): add group control support
fix(sensor): correct energy calculation overflow
refactor: move register_listener to entity objects
chore(release): bump version to 0.2.0

# Good with body
refactor: move register_listener to entity objects

- Add register_listener() to Device/Group/Scene in SDK
- Remove gateway parameter from integration entities
- Simplify all-light creation from 14 lines to 1 line

# Bad - too vague
refactor: cleanup
fix: bug fixes
```

### Pull Request Process

1. **Create feature branch** from main branch
2. **Create PR** with clear description and test plan
3. **Update documentation** (README.md) if needed
4. **Merge using squash and merge** strategy

### Release Process

1. **Update version** in `manifest.json` and `pyproject.toml`
2. **Update CHANGELOG.md** with release notes:
   - Use simplified structure: Added, Fixed, Technical
   - Include issue references (#123) for user-facing changes
   - Include commit hashes (abc1234) for technical changes without issues
   - Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
   - Update version links at bottom of changelog
3. **Commit changes** to main branch: `chore(release): bump version to x.y.z`
4. **Create and push tag**: `git tag v{version} && git push upstream v{version}`
5. **Create GitHub release**: `gh release create v{version} -R {owner}/{repo} --title "v{version}" --notes "..."`
   - Copy release notes from CHANGELOG.md with same structure
6. **Push to all remote repositories** if using multiple remotes
7. **Follow semantic versioning**: MAJOR.MINOR.PATCH

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
