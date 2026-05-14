# SSE Events Reference

Real-time room updates are delivered over a Server-Sent Events stream at
`GET /room/{code}/stream`. This document is the authoritative protocol
reference for frontend clients.

---

## Connection Setup

```
GET /room/{code}/stream
Accept: text/event-stream
Cookie: session=<session-cookie>
```

- A valid session cookie is required. The server returns `401` if absent.
- The client **must** send `Accept: text/event-stream` (most SSE browser
  implementations do this automatically).
- The server responds with `Content-Type: text/event-stream` and keeps the
  connection open indefinitely.
- The response carries `Cache-Control: no-cache` and `X-Accel-Buffering: no`
  to prevent proxy buffering.

---

## `session_bootstrap` Handshake

The very first event on every fresh connection (no `Last-Event-ID` / no
`after_event_id`) is always `session_bootstrap`. Clients must parse it to
initialise local state before processing subsequent events.

### Payload

```json
{
  "event_type": "session_bootstrap",
  "instance_id": "<hex string>",
  "ready": true,
  "genre": "All",
  "solo": false,
  "hide_watched": false,
  "replay_boundary": 42
}
```

| Field             | Type    | Description                                                               |
| ----------------- | ------- | ------------------------------------------------------------------------- |
| `event_type`      | string  | Always `"session_bootstrap"`.                                             |
| `instance_id`     | string  | Unique identifier for this session instance.                              |
| `ready`           | boolean | Whether both players have joined and the deck is ready to swipe.          |
| `genre`           | string  | Current genre filter, e.g. `"All"`, `"Action"`.                           |
| `solo`            | boolean | `true` when this is a solo (single-player) room.                          |
| `hide_watched`    | boolean | Whether already-watched titles are excluded from the deck.                |
| `replay_boundary` | integer | Highest `event_id` currently in the ledger; use as the cursor for replay. |

The SSE frame carrying `session_bootstrap` also has an `id:` field set to
`replay_boundary`. Clients may use this as the initial `Last-Event-ID` for
future reconnections.

---

## Event Reference

Every event delivered from the ledger (all types except `session_bootstrap`
and `session_reset`) includes two envelope fields merged at the top level:

| Field        | Type    | Description                                   |
| ------------ | ------- | --------------------------------------------- |
| `event_id`   | integer | Monotonic per-instance event sequence number. |
| `event_type` | string  | Discriminator — one of the names below.       |

### `session_ready`

Emitted when both players have joined and the room is ready to swipe (or
immediately on creation for solo rooms).

```json
{
  "event_id": 1,
  "event_type": "session_ready"
}
```

For solo rooms the payload also includes:

```json
{
  "event_id": 1,
  "event_type": "session_ready",
  "solo": true
}
```

| Field      | Type    | Description                                  |
| ---------- | ------- | -------------------------------------------- |
| `event_id` | integer | Event sequence number.                       |
| `solo`     | boolean | Present and `true` only for solo-mode rooms. |

### `session_closed`

Emitted when the room host quits. This is a **terminal event** — the client
should stop swiping and redirect the user to the home screen. The stream ends
after this event.

```json
{
  "event_id": 5,
  "event_type": "session_closed"
}
```

### `genre_changed`

Emitted when the active genre filter changes. The client should refresh any
genre UI and discard deck state for the previous genre.

```json
{
  "event_id": 3,
  "event_type": "genre_changed",
  "genre": "Action"
}
```

| Field   | Type   | Description                               |
| ------- | ------ | ----------------------------------------- |
| `genre` | string | New genre name, e.g. `"Action"`, `"All"`. |

### `hide_watched_changed`

Emitted when the "hide watched" filter is toggled. The client should refresh
the deck accordingly.

```json
{
  "event_id": 4,
  "event_type": "hide_watched_changed",
  "hide_watched": true
}
```

| Field          | Type    | Description                            |
| -------------- | ------- | -------------------------------------- |
| `hide_watched` | boolean | New value of the hide-watched setting. |

### `match_found`

Emitted when both players swipe right on the same title. The client should
surface a match notification to the user.

```json
{
  "event_id": 7,
  "event_type": "match_found",
  "media_id": "12345",
  "title": "The Dark Knight",
  "thumb": "http://jellyfin.local/Items/12345/Images/Primary",
  "media_type": "movie",
  "rating": "8.9",
  "duration": 7380,
  "year": "2008",
  "deep_link": "http://jellyfin.local/web/index.html#!/details?id=12345"
}
```

| Field        | Type              | Description                                                    |
| ------------ | ----------------- | -------------------------------------------------------------- |
| `media_id`   | string            | Jellyfin item ID.                                              |
| `title`      | string or null    | Media title; `null` if unavailable in catalog.                 |
| `thumb`      | string or null    | Thumbnail URL; `null` if unavailable in catalog.               |
| `media_type` | string            | `"movie"` or `"tv_show"`.                                      |
| `rating`     | string            | Community rating as a string, e.g. `"8.9"`, or `""` if absent. |
| `duration`   | integer or string | Duration in seconds (integer), or `""` if absent.              |
| `year`       | string            | Release year as a string, e.g. `"2008"`, or `""` if absent.    |
| `deep_link`  | string            | Direct Jellyfin web player URL for this title.                 |

---

## Cursor and Replay Protocol

### Fields

| Mechanism         | Where                     | Description                                                                                                                                                   |
| ----------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Last-Event-ID`   | Request header            | The `event_id` of the last event the client processed. The server replays all events after this ID.                                                           |
| `after_event_id`  | Query parameter           | Alternative to `Last-Event-ID` for clients that cannot set headers (e.g. `EventSource` in some browsers). Takes precedence only if `Last-Event-ID` is absent. |
| `replay_boundary` | `session_bootstrap` field | The highest event ID in the ledger at connection time. Use this as the initial cursor so reconnects don't replay events the client already has.               |

### How to use

1. On first connect (no cursor), receive `session_bootstrap` and store its
   `replay_boundary` value.
2. On every subsequent event, update your stored cursor to the event's
   `event_id`.
3. When reconnecting (e.g. after a network drop), open the stream with
   `Last-Event-ID: <stored cursor>` to receive only events you missed.

---

## Reconnection Behavior

If the client reconnects with a cursor that is older than the server's replay
window (i.e., no events exist after that cursor in the ledger), the server
emits `session_reset` with `reason: "stale_cursor"` and closes the stream.

```json
{
  "event_type": "session_reset",
  "reason": "stale_cursor"
}
```

The client should drop all local state, clear the stored cursor, and reconnect
without a cursor to receive a fresh `session_bootstrap`.

---

## Terminal Events

Two event types signal that the session is permanently over. After receiving
either, the client **must not** reconnect.

| Event            | Reason                           | Client action                               |
| ---------------- | -------------------------------- | ------------------------------------------- |
| `session_closed` | Host quit the room               | End the session; redirect to home screen.   |
| `session_reset`  | Stale cursor or instance changed | Drop local state; reconnect without cursor. |

`session_reset` is **not** a terminal event in the destructive sense — it
instructs the client to reset and reconnect. `session_closed` is truly
terminal and the client should treat it as session end.

---

## Keep-Alive

To prevent proxies and load balancers from closing idle connections, the
server sends an SSE comment frame approximately every 15 seconds when no
events are emitted:

```
: ping
```

SSE comment frames (lines beginning with `:`) carry no data and must be
silently ignored by compliant clients. Browser `EventSource` implementations
handle this automatically.
