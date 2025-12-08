# Change: Improve Integration Robustness and Performance

## Why

GitHub Issue #63 reports critical stability problems causing Home Assistant crashes. Analysis of user logs reveals two distinct failure scenarios:

### Scenario 1: Runtime MQTT Disconnection → Segfault

When MQTT connections are reset during runtime, Home Assistant crashes with Python segfault (Signal 11):

```
[ERROR] [paho.mqtt.client] failed to receive on socket: [Errno 104] Connection reset by peer
[WARNING] [PySrDaliGateway.gateway] Gateway 26250205591A: Unexpected MQTT disconnection - Reason code: Unspecified error
...
[INFO] Home Assistant Core finish process exit code 256
[INFO] Home Assistant Core finish process received signal 11
```

### Scenario 2: Startup Connection Failures → Log Flooding

When gateways are unreachable during startup, the integration repeatedly attempts connections:

```
[ERROR] Network error connecting to gateway 26250205591A: [Errno 113] Host is unreachable
[ERROR] Network error connecting to gateway 362502056106: [Errno 113] Host is unreachable
[ERROR] Network error connecting to gateway 22250205551A: [Errno 113] Host is unreachable
... (repeats for each gateway, filling logs)
```

### Impact

- Complete system crashes every 2-18 hours (Scenario 1)
- Database corruption from unclean shutdowns
- Log flooding when gateways are temporarily offline (Scenario 2)
- Loss of automation reliability

### Root Causes Identified

1. **Thread safety violations**: paho-mqtt callbacks run in a separate thread but directly invoke Home Assistant entity updates via `schedule_update_ha_state()`, which must run on the HA event loop thread. See [HA Thread Safety](https://developers.home-assistant.io/docs/asyncio_thread_safety/).
2. **Unsafe asyncio.Event usage**: `asyncio.Event.set()` called from paho-mqtt thread (synchronous context), not thread-safe. See [Python asyncio and threads](https://docs.python.org/3/library/asyncio-dev.html#concurrency-and-multithreading).
3. **No automatic reconnection**: When gateway disconnects at runtime, entities become permanently unavailable.
4. **Aggressive retry without backoff**: `ConfigEntryNotReady` triggers immediate retries, flooding logs when gateway is offline.

## What Changes

### SDK Library (PySrDaliGateway) Changes

- **Thread-safe callback invocation**: Use `loop.call_soon_threadsafe()` to dispatch callbacks from MQTT thread to asyncio event loop
- **Thread-safe asyncio.Event**: Replace direct `Event.set()` with thread-safe mechanism
- **Automatic reconnection**: Implement exponential backoff reconnection when connection is lost at runtime
- **Connection state machine**: Add explicit states (DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING) with proper transitions

### Integration Changes

- **Thread-safe entity updates**: Ensure entity callbacks are decorated with `@callback` and only update state when called from event loop thread
- **Graceful startup failures**: Use `ConfigEntryNotReady` with appropriate messages; reduce log level for expected failures
- **Improved availability tracking**: Log state changes once per transition (per HA Silver tier requirements)
- **Runtime reconnection handling**: Handle gateway reconnection events, restore entity availability

## Impact

- Affected specs: New capability `gateway-connection` (connection management and robustness)
- Affected code:
  - SDK: `PySrDaliGateway/gateway.py` (thread-safe callbacks and reconnection)
  - Integration: `__init__.py`, `entity.py` (minor updates for thread safety)
- **BREAKING**: SDK API changes require version bump (0.19.0)
- Risk: Medium - focused changes in SDK, minimal integration changes

## References

- [GitHub Issue #63](https://github.com/maginawin/ha-dali-center/issues/63)
- [HA Thread Safety Guidelines](https://developers.home-assistant.io/docs/asyncio_thread_safety/) - **Critical**: explains why `schedule_update_ha_state()` must run on event loop
- [HA Handling Offline Devices](https://developers.home-assistant.io/docs/integration_setup_failures/) - how to use `ConfigEntryNotReady`
- [Python asyncio Concurrency and Multithreading](https://docs.python.org/3/library/asyncio-dev.html#concurrency-and-multithreading) - explains `call_soon_threadsafe()`
- [paho-mqtt Callbacks](https://eclipse.dev/paho/files/paho.mqtt.python/html/index.html#callbacks) - confirms callbacks run in network thread
- [HA Integration Quality Scale - Silver Tier](https://developers.home-assistant.io/docs/core/integration-quality-scale/) - availability logging requirements
