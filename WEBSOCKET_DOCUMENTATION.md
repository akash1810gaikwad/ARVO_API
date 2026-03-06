# ARVO WebSocket API Documentation

## Overview

ARVO uses WebSocket connections for real-time communication between parent apps and child devices. This enables live location tracking, SOS alerts, chat messaging, and remote commands.

**Base URL:** `wss://api.arvomobile.co.uk`

---

## Connection URLs

| Endpoint | URL | Auth Method |
|----------|-----|-------------|
| Parent | `wss://api.arvomobile.co.uk/ws/parent?token=<JWT_TOKEN>` | JWT token (query param) |
| Child | `wss://api.arvomobile.co.uk/ws/child?msisdn=<MSISDN>` | MSISDN (query param) |

> For local development, use `ws://localhost:8000` instead of `wss://api.arvomobile.co.uk`

---

## Authentication

### Parent Endpoint
- Requires a valid JWT token passed as the `token` query parameter
- The token must contain a `sub` claim with the customer ID
- The customer must exist and be active in the database
- If the token is invalid or the customer is inactive, the connection is closed with code `1008`

### Child Endpoint
- Requires a valid `msisdn` query parameter
- The MSISDN must belong to an active ChildSimCard in the database
- If the MSISDN is invalid or inactive, the connection is closed with code `1008`

---

## Parent WebSocket (`/ws/parent`)

### Connection

```
wss://api.arvomobile.co.uk/ws/parent?token=eyJhbGciOiJIUzI1NiIs...
```

### On Connect (Server -> Parent)

The server sends a welcome message immediately after connection:

```json
{
  "type": "connected",
  "message": "Connected to parent WebSocket",
  "customer_id": 123,
  "online_children": [
    {
      "msisdn": "447942351146",
      "child_name": "Emma",
      "connected_at": "2026-03-05T10:30:00"
    }
  ]
}
```

### Messages Parent Can SEND (Parent -> Server)

#### 1. Ping (keep-alive)

```json
{
  "type": "ping"
}
```

**Response:**
```json
{
  "type": "pong"
}
```

#### 2. Join Room

```json
{
  "type": "join",
  "room": "room_name"
}
```

**Response:**
```json
{
  "type": "joined",
  "room": "room_name"
}
```

#### 3. Send Command to Child

Send a command to a specific child device (e.g., lock phone, enable/disable apps).

```json
{
  "type": "command",
  "to": "447942351146",
  "action": "lock_phone",
  "data": {
    "duration": 3600
  }
}
```

**Response:**
```json
{
  "type": "command_sent",
  "to": "447942351146",
  "action": "lock_phone"
}
```

#### 4. Send Chat Message to Child

```json
{
  "type": "chat",
  "to": "447942351146",
  "message": "Time to come home!"
}
```

**Response:**
```json
{
  "type": "chat_sent",
  "to": "447942351146"
}
```

#### 5. Request Child's Location

```json
{
  "type": "location_request",
  "msisdn": "447942351146"
}
```

**Response:**
```json
{
  "type": "location_requested",
  "msisdn": "447942351146"
}
```

#### 6. Get Online Children

```json
{
  "type": "get_online_children"
}
```

**Response:**
```json
{
  "type": "online_children",
  "children": [
    {
      "msisdn": "447942351146",
      "child_name": "Emma",
      "connected_at": "2026-03-05T10:30:00"
    }
  ]
}
```

### Messages Parent Can RECEIVE (Server -> Parent)

#### 1. Child Connected

Received when one of your children comes online.

```json
{
  "type": "child_connected",
  "msisdn": "447942351146",
  "child_name": "Emma",
  "timestamp": "2026-03-05T10:30:00"
}
```

#### 2. Child Disconnected

```json
{
  "type": "child_disconnected",
  "msisdn": "447942351146",
  "child_name": "Emma",
  "timestamp": "2026-03-05T10:35:00"
}
```

#### 3. Location Update (from child)

```json
{
  "type": "location",
  "msisdn": "447942351146",
  "child_name": "Emma",
  "lat": 51.5074,
  "lng": -0.1278,
  "battery": 85,
  "speed": 0,
  "accuracy": 10.5,
  "timestamp": "2026-03-05T10:31:00"
}
```

#### 4. SOS Alert (from child)

```json
{
  "type": "sos",
  "msisdn": "447942351146",
  "child_name": "Emma",
  "message": "Emergency SOS",
  "lat": 51.5074,
  "lng": -0.1278,
  "timestamp": "2026-03-05T10:32:00"
}
```

#### 5. Chat Message (from child)

```json
{
  "type": "chat",
  "from": "447942351146",
  "from_name": "Emma",
  "message": "I'm at school!",
  "timestamp": "2026-03-05T10:33:00"
}
```

#### 6. Alert (from system)

```json
{
  "type": "alert",
  "alert_type": "geofence_exit",
  "msisdn": "447942351146",
  "message": "Emma left the school zone"
}
```

---

## Child WebSocket (`/ws/child`)

### Connection

```
wss://api.arvomobile.co.uk/ws/child?msisdn=447942351146
```

### On Connect (Server -> Child)

```json
{
  "type": "connected",
  "message": "Connected to child WebSocket",
  "msisdn": "447942351146",
  "child_name": "Emma"
}
```

### Messages Child Can SEND (Child -> Server)

#### 1. Ping (keep-alive)

```json
{
  "type": "ping"
}
```

**Response:**
```json
{
  "type": "pong"
}
```

#### 2. Join Room

```json
{
  "type": "join",
  "room": "room_name"
}
```

**Response:**
```json
{
  "type": "joined",
  "room": "room_name"
}
```

#### 3. Send Location Update

```json
{
  "type": "location",
  "lat": 51.5074,
  "lng": -0.1278,
  "battery": 85,
  "speed": 0,
  "accuracy": 10.5,
  "provider": "gps"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | Yes | Latitude |
| lng | float | Yes | Longitude |
| battery | int | No | Battery percentage (0-100) |
| speed | float | No | Speed in m/s (default: 0) |
| accuracy | float | No | GPS accuracy in meters |
| provider | string | No | Location provider (default: "gps") |

**Response:**
```json
{
  "type": "location_saved",
  "message": "Location updated"
}
```

The location is saved to the database AND forwarded to the parent in real-time.

#### 4. Send SOS Alert

```json
{
  "type": "sos",
  "lat": 51.5074,
  "lng": -0.1278,
  "message": "I need help!"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | No | Latitude at time of SOS |
| lng | float | No | Longitude at time of SOS |
| message | string | No | SOS message (default: "Emergency SOS") |

**Response:**
```json
{
  "type": "sos_received",
  "message": "SOS alert sent to parent"
}
```

The SOS alert is saved to the database as a ChildAlert AND forwarded to the parent.

#### 5. Send Chat Message to Parent

```json
{
  "type": "chat",
  "message": "I'm at school!"
}
```

**Response:**
```json
{
  "type": "chat_sent",
  "message": "Message sent to parent"
}
```

### Messages Child Can RECEIVE (Server -> Child)

#### 1. Command from Parent

```json
{
  "type": "command",
  "action": "lock_phone",
  "data": {
    "duration": 3600
  },
  "timestamp": "2026-03-05T10:31:00"
}
```

#### 2. Chat Message from Parent

```json
{
  "type": "chat",
  "from": "parent",
  "from_name": "John Smith",
  "message": "Time to come home!",
  "timestamp": "2026-03-05T10:32:00"
}
```

#### 3. Location Request from Parent

```json
{
  "type": "location_request",
  "timestamp": "2026-03-05T10:33:00"
}
```

When received, the child device should respond by sending a location update.

---

## Connection Flow Diagram

```
Parent App                    Server                    Child Device
    |                           |                           |
    |--- Connect (JWT token) -->|                           |
    |<-- connected + online ----|                           |
    |    children list          |                           |
    |                           |<-- Connect (MSISDN) ------|
    |                           |--- connected ------------>|
    |<-- child_connected -------|                           |
    |                           |                           |
    |                           |<-- location --------------|
    |<-- location --------------|--- location_saved ------->|
    |                           |                           |
    |--- location_request ----->|                           |
    |<-- location_requested ----|--- location_request ----->|
    |                           |<-- location --------------|
    |<-- location --------------|--- location_saved ------->|
    |                           |                           |
    |--- chat ----------------->|                           |
    |<-- chat_sent -------------|--- chat ----------------->|
    |                           |                           |
    |                           |<-- sos -------------------|
    |<-- sos -------------------|--- sos_received --------->|
    |                           |                           |
    |--- command --------------->|                          |
    |<-- command_sent ----------|--- command --------------->|
    |                           |                           |
    |                           |<-- disconnect ------------|
    |<-- child_disconnected ----|                           |
```

---

## Error Handling

### Close Codes

| Code | Reason | Description |
|------|--------|-------------|
| 1008 | Invalid token | JWT token is invalid or expired (parent) |
| 1008 | Invalid customer | Customer not found or inactive (parent) |
| 1008 | Invalid MSISDN | MSISDN not found or inactive (child) |
| 1006 | Abnormal closure | Connection lost unexpectedly |

### Reconnection Strategy

Clients should implement reconnection with exponential backoff:

1. Wait 1 second, reconnect
2. Wait 2 seconds, reconnect
3. Wait 4 seconds, reconnect
4. Wait 8 seconds, reconnect
5. Max wait: 30 seconds between attempts

---

## React Native Client Example

### Child Device Connection

```javascript
const connectWebSocket = (msisdn) => {
  const ws = new WebSocket(`wss://api.arvomobile.co.uk/ws/child?msisdn=${msisdn}`);

  ws.onopen = () => {
    console.log('Connected to WebSocket');
  };

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    switch (message.type) {
      case 'connected':
        console.log('Welcome:', message.child_name);
        break;
      case 'command':
        handleCommand(message.action, message.data);
        break;
      case 'chat':
        showChatMessage(message.from_name, message.message);
        break;
      case 'location_request':
        sendCurrentLocation(ws);
        break;
      case 'pong':
        break;
    }
  };

  ws.onclose = (event) => {
    console.log('Disconnected:', event.code, event.reason);
    // Implement reconnection logic here
  };

  // Send location update
  const sendLocation = (lat, lng, battery) => {
    ws.send(JSON.stringify({
      type: 'location',
      lat: lat,
      lng: lng,
      battery: battery,
      speed: 0,
      accuracy: 10,
      provider: 'gps'
    }));
  };

  // Send SOS
  const sendSOS = (lat, lng) => {
    ws.send(JSON.stringify({
      type: 'sos',
      lat: lat,
      lng: lng,
      message: 'Emergency SOS'
    }));
  };

  // Keep-alive ping every 30 seconds
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 30000);

  return { ws, sendLocation, sendSOS, pingInterval };
};
```

### Parent App Connection

```javascript
const connectParentWebSocket = (token) => {
  const ws = new WebSocket(`wss://api.arvomobile.co.uk/ws/parent?token=${token}`);

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    switch (message.type) {
      case 'connected':
        console.log('Online children:', message.online_children);
        break;
      case 'child_connected':
        console.log(`${message.child_name} is online`);
        break;
      case 'child_disconnected':
        console.log(`${message.child_name} went offline`);
        break;
      case 'location':
        updateChildLocation(message.msisdn, message.lat, message.lng);
        break;
      case 'sos':
        showSOSAlert(message.child_name, message.message, message.lat, message.lng);
        break;
      case 'chat':
        showChatMessage(message.from_name, message.message);
        break;
    }
  };

  // Request child location
  const requestLocation = (msisdn) => {
    ws.send(JSON.stringify({
      type: 'location_request',
      msisdn: msisdn
    }));
  };

  // Send command to child
  const sendCommand = (msisdn, action, data = {}) => {
    ws.send(JSON.stringify({
      type: 'command',
      to: msisdn,
      action: action,
      data: data
    }));
  };

  // Send chat to child
  const sendChat = (msisdn, message) => {
    ws.send(JSON.stringify({
      type: 'chat',
      to: msisdn,
      message: message
    }));
  };

  return { ws, requestLocation, sendCommand, sendChat };
};
```
