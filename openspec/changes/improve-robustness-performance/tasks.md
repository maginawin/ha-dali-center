# Tasks: Improve Integration Robustness and Performance

## Phase 1: SDK Changes (PySrDaliGateway)

### 1.1 Thread-Safe Callback Infrastructure

- [x] 1.1.1 Add optional `loop` parameter to `DaliGateway.__init__`
- [x] 1.1.2 Create `_dispatch_callback()` helper using `call_soon_threadsafe()`
- [x] 1.1.3 Update `_notify_listeners()` to use `_dispatch_callback()`
- [x] 1.1.4 Update `asyncio.Event.set()` calls to be thread-safe

### 1.2 Connection State Machine

- [x] 1.2.1 Create `ConnectionState` enum (DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING)
- [x] 1.2.2 Add `_connection_state` and `is_connected` properties
- [x] 1.2.3 Update `connect()`, `_on_connect`, `_on_disconnect` for state transitions

### 1.3 Auto-Reconnection

- [x] 1.3.1 Implement `_schedule_reconnect()` with exponential backoff
- [x] 1.3.2 Update `_on_disconnect` to trigger reconnection
- [x] 1.3.3 Add `stop_reconnection()` for clean shutdown

### 1.4 SDK Release

- [ ] 1.4.1 Add unit tests for thread-safe callbacks
- [ ] 1.4.2 Update version to 0.19.0
- [ ] 1.4.3 Release to PyPI

## Phase 2: Integration Changes

### 2.1 Gateway Initialization

- [x] 2.1.1 Update `async_setup_entry` to pass `hass.loop` to gateway
- [ ] 2.1.2 Update `requirements` to SDK 0.19.0

### 2.2 Logging Improvements

- [x] 2.2.1 Reduce connection failure log level from ERROR to WARNING
- [x] 2.2.2 Remove stack traces from expected connection errors
- [ ] 2.2.3 Add "one log per state change" for availability

### 2.3 Integration Release

- [ ] 2.3.1 Test with unreachable gateway (verify no log flooding)
- [ ] 2.3.2 Test MQTT disconnection (verify no crash)
- [ ] 2.3.3 Update version to 0.12.0

## Dependencies

- Phase 2 depends on Phase 1 (SDK must be released first)

## Verification

- [ ] No segfaults during MQTT disconnection
- [ ] Clean logs when gateway offline
- [ ] Auto-reconnection works
