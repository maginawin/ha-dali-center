# Gateway Connection Management

## ADDED Requirements

### Requirement: Thread-Safe Callback Dispatch

The SDK SHALL dispatch all callbacks to registered listeners on the event loop thread when an event loop reference is provided during initialization.

#### Scenario: Callback invoked from MQTT thread

- **GIVEN** a gateway initialized with an event loop reference
- **WHEN** a callback is triggered from the paho-mqtt thread (e.g., on_disconnect)
- **THEN** the listener callback SHALL be scheduled via `call_soon_threadsafe()` and executed on the event loop thread

#### Scenario: Backward compatibility without event loop

- **GIVEN** a gateway initialized without an event loop reference
- **WHEN** a callback is triggered
- **THEN** the listener callback SHALL be invoked directly (legacy behavior)

### Requirement: Thread-Safe Event Signaling

The SDK SHALL use thread-safe mechanisms when signaling asyncio.Event objects from the paho-mqtt thread.

#### Scenario: Connection event signaling

- **GIVEN** a gateway with an event loop reference
- **WHEN** `_on_connect` callback sets `_connection_event`
- **THEN** the event SHALL be set via `call_soon_threadsafe()` to avoid race conditions

### Requirement: Connection State Machine

The SDK SHALL maintain explicit connection states and provide state transition notifications.

#### Scenario: Initial state

- **GIVEN** a newly created gateway instance
- **WHEN** checking connection state before calling `connect()`
- **THEN** the state SHALL be `DISCONNECTED`

#### Scenario: Successful connection

- **GIVEN** a gateway in `DISCONNECTED` state
- **WHEN** `connect()` is called and MQTT connection succeeds
- **THEN** the state SHALL transition through `CONNECTING` to `CONNECTED`

#### Scenario: Unexpected disconnection

- **GIVEN** a gateway in `CONNECTED` state
- **WHEN** the MQTT connection is lost unexpectedly (socket error, keep-alive timeout)
- **THEN** the state SHALL transition to `RECONNECTING`

### Requirement: Automatic Reconnection

The SDK SHALL automatically attempt to reconnect when an unexpected disconnection occurs, using exponential backoff.

#### Scenario: Reconnection with backoff

- **GIVEN** a gateway that has transitioned to `RECONNECTING` state
- **WHEN** reconnection attempts are made
- **THEN** delays SHALL follow exponential backoff (1s, 2s, 4s, ... up to 60s max)

#### Scenario: Reconnection success

- **GIVEN** a gateway in `RECONNECTING` state
- **WHEN** a reconnection attempt succeeds
- **THEN** the state SHALL transition to `CONNECTED`
- **AND** MQTT subscriptions SHALL be restored
- **AND** listeners SHALL be notified

#### Scenario: Clean disconnect stops reconnection

- **GIVEN** a gateway in `RECONNECTING` state
- **WHEN** `disconnect()` is called explicitly
- **THEN** pending reconnection attempts SHALL be cancelled

### Requirement: Reduced Log Noise

The integration SHALL minimize log output during expected failure conditions.

#### Scenario: Connection failure logging

- **GIVEN** a gateway that fails to connect during setup
- **WHEN** `ConfigEntryNotReady` is raised
- **THEN** the log SHALL use WARNING level (not ERROR)
- **AND** the log SHALL NOT contain a full stack trace

#### Scenario: Availability change logging

- **GIVEN** an entity tracking gateway availability
- **WHEN** availability changes
- **THEN** a log entry SHALL be emitted once per state transition (not on every update)
