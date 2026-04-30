# Phase 28: SSE Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 28-coverage-enforcement (v1.7 SSE Reliability)
**Areas discussed:** Poll Jitter, Heartbeat Mechanism, Room Disappearance, gevent Compatibility, Test Strategy
**Mode:** `--auto --all --batch` (all decisions auto-selected)

---

## Poll Jitter (SSE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Random uniform jitter | `time.sleep(POLL + random.uniform(0, 0.5))` — simple, effective, stdlib only | ✓ |
| Decorrelated jitter | Exponential backoff with jitter — overkill for fixed-interval polling | |
| Deterministic stagger | Per-client offset based on session ID — requires client identity | |

**Auto-selected:** Random uniform jitter (recommended default)
**Notes:** stdlib `random` module, no new deps. Jitter applies to every sleep cycle including error recovery path.

---

## Heartbeat Mechanism (SSE-02)

| Option | Description | Selected |
|--------|-------------|----------|
| SSE comment heartbeat | Yield `: ping\n\n` every ~15s — invisible to EventSource clients | ✓ |
| Data event heartbeat | Yield `data: {"type":"ping"}\n\n` — requires client-side handling | |
| Dual heartbeat | Both comment and data event — redundant complexity | |

**Auto-selected:** SSE comment heartbeat (recommended default)
**Notes:** 15-second interval provides ~4 heartbeats/min, well within proxy idle timeouts. No client-side changes needed.

---

## Room Disappearance Handling (SSE-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Immediate exit (existing) | Current Phase 27 behavior: yield `closed: True` and return on null row | ✓ |
| Retry then exit | Retry query N times before exiting — adds latency | |
| Error event then exit | Yield error event before closing — client may not handle | |

**Auto-selected:** Immediate exit (recommended default — already implemented)
**Notes:** Phase 27 refactored code already exits immediately on null row. SSE-03 is verified and tested.

---

## gevent Compatibility (Deferred from Phase 27)

| Option | Description | Selected |
|--------|-------------|----------|
| Conditional gevent.sleep() | `try: from gevent import sleep as gevent_sleep` with runtime fallback to `time.sleep` | ✓ |
| Always use time.sleep() | Simpler but blocks gevent workers | |
| Always use gevent.sleep() | Fails in test environments without gevent | |

**Auto-selected:** Conditional gevent.sleep() (recommended default)
**Notes:** Gracefully degrades in test/dev environments. Production gunicorn+gevent gets non-blocking sleep.

---

## the agent's Discretion

- Variable naming for heartbeat state tracker (`_last_event_time` vs `last_heartbeat`)
- Whether to extract jitter/heartbeat logic into helper functions or keep inline
- Whether to add a comment explaining the gevent sleep fallback
- Ordering of jitter calculation vs data event check

## Deferred Ideas

- SSE reconnection logic on the client side (EventSource auto-reconnects by spec)
- Configurable heartbeat interval (hard-code 15s for now)
- Message bus for `last_match_data` overwrites (future milestone)