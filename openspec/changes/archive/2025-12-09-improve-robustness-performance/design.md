# Design: Improve Integration Robustness and Performance

## Context

The current integration has critical thread safety issues causing Python segfaults. This document explains the problem mechanism and the fix approach.

## Problem Explanation

### Why Does Segfault Happen?

Home Assistant runs on a **single-threaded event loop** (asyncio). All entity state updates must happen on this thread because HA's internal data structures are **not thread-safe**.

However, `paho-mqtt` runs its network loop in a **separate thread**. When MQTT events occur (connect, disconnect, message), callbacks are invoked from this network thread.

**Current problematic flow:**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HOME ASSISTANT PROCESS                            │
│                                                                          │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │              MAIN THREAD (Event Loop)                           │   │
│   │                                                                  │   │
│   │    Entity._attr_available ◀──┬── Accessed by two threads!       │   │
│   │    Entity._attr_brightness   │   (Race Condition)               │   │
│   │    HA internal state ────────┤                                   │   │
│   │                              │                                   │   │
│   └──────────────────────────────┼───────────────────────────────────┘   │
│                                  │                                        │
│   ┌──────────────────────────────┼───────────────────────────────────┐   │
│   │              PAHO-MQTT THREAD                                     │   │
│   │                              │                                    │   │
│   │    _on_disconnect() ─────────┘                                   │   │
│   │         │                                                         │   │
│   │         ▼                                                         │   │
│   │    _notify_listeners()                                           │   │
│   │         │                                                         │   │
│   │         ▼                                                         │   │
│   │    entity._handle_availability(False)                            │   │
│   │         │                                                         │   │
│   │         ▼                                                         │   │
│   │    self._attr_available = False  ◀── Writing from wrong thread! │   │
│   │         │                                                         │   │
│   │         ▼                                                         │   │
│   │    schedule_update_ha_state()    ◀── 💥 Triggers HA state update │   │
│   │                                       from wrong thread = SEGFAULT│   │
│   └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Timeline of a Crash

```
Time ──────────────────────────────────────────────────────────────────────▶

16:11:44  Gateway 362502056106: Keep alive timeout
          └─ paho-mqtt detects connection lost

16:11:49  [paho.mqtt.client] failed to receive on socket: [Errno 104] Connection reset by peer
          └─ Socket error triggers _on_disconnect callback

16:11:49  _on_disconnect() runs in paho-mqtt thread
               │
               └─▶ _notify_listeners(ONLINE_STATUS, False)
                        │
                        └─▶ entity._handle_availability(False)
                                 │
                                 ├─▶ self._attr_available = False  ← Writing to shared memory
                                 │
                                 └─▶ schedule_update_ha_state()    ← 💥 Triggers HA update
                                          │
                                          └─▶ HA tries to update state from non-main thread
                                               │
                                               └─▶ Memory corruption → SIGSEGV (Signal 11)

11:57:25  Home Assistant Core finish process received signal 11
          └─ Process crashed
```

### The Fix: Thread-Safe Callback Dispatch

**Solution**: Use `loop.call_soon_threadsafe()` to schedule callbacks on the event loop thread instead of executing them directly.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HOME ASSISTANT PROCESS                            │
│                                                                          │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │              MAIN THREAD (Event Loop)                           │   │
│   │                                                                  │   │
│   │    ┌─────────────────────────────────────────────────────────┐ │   │
│   │    │              Event Queue (thread-safe)                   │ │   │
│   │    │                                                          │ │   │
│   │    │   [cb1] [cb2] [cb3] ...  ◀── Callbacks queued safely    │ │   │
│   │    │     │                                                    │ │   │
│   │    └─────┼────────────────────────────────────────────────────┘ │   │
│   │          │                                                       │   │
│   │          ▼ Event loop executes callback when safe               │   │
│   │                                                                  │   │
│   │    entity._handle_availability(False)  ✅ Runs on correct thread│   │
│   │         │                                                        │   │
│   │         ▼                                                        │   │
│   │    schedule_update_ha_state()          ✅ Safe!                 │   │
│   │                                                                  │   │
│   └──────────────────────────────────────────────────────────────────┘   │
│                              ▲                                            │
│                              │ call_soon_threadsafe()                    │
│                              │ (thread-safe queue insertion)             │
│   ┌──────────────────────────┼───────────────────────────────────────┐   │
│   │              PAHO-MQTT THREAD                                     │   │
│   │                          │                                        │   │
│   │    _on_disconnect() ─────┘                                       │   │
│   │         │                                                         │   │
│   │         ▼                                                         │   │
│   │    _notify_listeners()                                           │   │
│   │         │                                                         │   │
│   │         ▼                                                         │   │
│   │    loop.call_soon_threadsafe(listener, data)  ✅ No direct call!│   │
│   │                                                                   │   │
│   └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key References

| Topic | Why It Matters |
|-------|----------------|
| [HA Thread Safety](https://developers.home-assistant.io/docs/asyncio_thread_safety/) | Explains why state updates must run on event loop |
| [Python asyncio Threads](https://docs.python.org/3/library/asyncio-dev.html#concurrency-and-multithreading) | Documents `call_soon_threadsafe()` |
| [paho-mqtt Callbacks](https://eclipse.dev/paho/files/paho.mqtt.python/html/index.html#callbacks) | Confirms callbacks run in network thread |
| [HA Handling Offline Devices](https://developers.home-assistant.io/docs/integration_setup_failures/) | How to use `ConfigEntryNotReady` |
| [HA Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) | Availability logging requirements |

## Decisions

### Decision 1: Thread-Safe Callback Dispatch in SDK

**What**: SDK uses `loop.call_soon_threadsafe()` to dispatch callbacks.

**Implementation in `gateway.py`**:

```python
def __init__(self, ..., loop: asyncio.AbstractEventLoop | None = None):
    self._loop = loop  # Store event loop reference

def _notify_listeners(self, event_type, dev_id, data):
    for listener in self._device_listeners.get(event_type, {}).get(dev_id, []):
        if self._loop is not None and self._loop.is_running():
            # Thread-safe: schedule callback on event loop
            self._loop.call_soon_threadsafe(listener, data)
        else:
            # Fallback for synchronous usage (backward compatible)
            listener(data)
```

**Why not use `hass.loop` directly?**: SDK should not depend on Home Assistant. The loop is passed during initialization.

### Decision 2: Thread-Safe asyncio.Event

**What**: Replace direct `Event.set()` with thread-safe version.

**Current (problematic)**:

```python
# Called from paho-mqtt thread
def _on_connect(self, ...):
    self._connection_event.set()  # NOT thread-safe!
```

**Fixed**:

```python
def _on_connect(self, ...):
    if self._loop is not None and self._loop.is_running():
        self._loop.call_soon_threadsafe(self._connection_event.set)
    else:
        self._connection_event.set()
```

### Decision 3: Auto-Reconnection with Exponential Backoff

**What**: When connection is lost unexpectedly, automatically reconnect.

**Parameters**:

- Initial delay: 1 second
- Max delay: 60 seconds
- Backoff: 2x per attempt
- Jitter: ±10%

**Sequence**: 1s → 2s → 4s → 8s → 16s → 32s → 60s → 60s → ...

### Decision 4: Simplified Integration Changes

**What**: Minimal changes to integration code.

**Changes needed**:

1. Pass `hass.loop` to gateway during initialization
2. Ensure entity callbacks use `@callback` decorator (already done)
3. Improve logging (reduce noise)

**NOT needed**:

- ~~DataUpdateCoordinator~~ - not required for push-based MQTT
- ~~Major entity refactoring~~ - current pattern is correct

## Risks

| Risk | Mitigation |
|------|------------|
| SDK API change (new `loop` parameter) | Make parameter optional with default `None` for backward compatibility |
| Reconnection storms | Exponential backoff with jitter |
| Testing thread safety | Add integration tests with mock MQTT broker |

## Test Plan

Thread safety issues are timing-dependent. The recommended approach is to simulate network disconnection:

```bash
# Block MQTT traffic to gateway
iptables -A OUTPUT -d <gateway_ip> -p tcp --dport 1883 -j DROP

# Wait 60 seconds for Keep alive timeout, observe if HA crashes

# Restore connection
iptables -D OUTPUT -d <gateway_ip> -p tcp --dport 1883 -j DROP
```

### Verification Checklist

#### Pre-fix

- [ ] Run network interruption test with current version
- [ ] Confirm Signal 11 crash occurs

#### Post-fix

- [ ] Repeat network interruption test (10+ iterations)
- [ ] No segfault occurs
- [ ] Entities become unavailable on disconnect
- [ ] Auto-reconnection succeeds when network restored
- [ ] Entities become available again

## Open Questions

1. Should reconnection parameters be configurable via config flow?
2. Should we expose connection health metrics for diagnostics?
