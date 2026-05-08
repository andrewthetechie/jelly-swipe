# Phase 38: Auth Persistence Conversion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 38-Auth Persistence Conversion
**Areas discussed:** Auth repository and service boundary, Session lifecycle semantics, Auth dependency behavior, Cleanup and invalid-session handling

---

## Auth repository and service boundary

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Thin repository plus thin service | Keep both layers small and focused | ✓ |
| Repository-only | Keep logic close to persistence | |
| Rich auth service over a narrow repository | Put most behavior into a service layer | |

**User's choice:** Thin repository plus thin service
**Notes:** The user wanted the auth pattern established without turning auth into an overly rich domain layer.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Service owns both | Service generates `session_id` and `created_at` | ✓ |
| Repository owns both | Insert path assigns all generated values | |
| Mixed | Split generation between service and repository | |

**User's choice:** Service owns both
**Notes:** The service should own auth record creation semantics.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| ORM model/entity | Return mapped models from lookup | |
| Small typed auth record / DTO | Return a narrow typed object for auth use | ✓ |
| Plain tuple | Preserve the current tuple shape | |

**User's choice:** Small typed auth record / DTO
**Notes:** The user wanted a cleaner shape than the current tuple without exposing ORM objects.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Service-only calls from routes/dependencies | Keep repository behind the service boundary | ✓ |
| Mixed direct access | Let simple routes use repository directly | |
| Swap internals only | Keep current module-level shape almost unchanged | |

**User's choice:** Routes and dependencies call the auth service only
**Notes:** This locks auth as the first real repository/service pattern.

---

## Session lifecycle semantics

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve 64-char hex exactly | Keep current session ID shape | |
| Any opaque ID is fine now | Session ID format can change | ✓ |
| Preserve externally, clean later | Keep current shape for now but allow future changes | |

**User's choice:** Any opaque ID is fine now
**Notes:** The greenfield migration does not need to preserve this incidental format.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Every new session creation | Match current cleanup timing | ✓ |
| Startup only | Remove per-request cleanup pressure | |
| Startup and creation | Clean in both places | |

**User's choice:** Cleanup on every new session creation
**Notes:** The current cleanup cadence remains preferred.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| Delete vault row and clear local state immediately | Match current hard-delete semantics | |
| Clear local state immediately, allow best-effort async vault cleanup | Decouple visible logout from storage cleanup | ✓ |
| Soft-delete / revoke | Preserve rows and mark them invalid | |

**User's choice:** Clear local state immediately, allow best-effort async vault cleanup
**Notes:** The user prioritized visible logout semantics over synchronous cleanup guarantees.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Treat as anonymous exactly like today | No special stale-session handling | |
| Treat as error and clear aggressively | Invalid session should be actively removed | ✓ |
| Treat as anonymous but clear stale state | Silent fallback plus cleanup | |

**User's choice:** Treat as error and clear aggressively
**Notes:** The user explicitly rejected a quiet anonymous fallback for stale session cookies.

---

## Auth dependency behavior

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Keep returning lightweight `AuthUser` | Preserve current dependency output contract | ✓ |
| Return the typed auth record directly | Surface the new DTO | |
| Return a richer auth context | Expand the dependency surface now | |

**User's choice:** Keep returning lightweight `AuthUser`
**Notes:** The user wanted auth internals to change without changing route-level consumer shape.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Inside `require_auth` | Dependency clears stale session state itself | ✓ |
| Dedicated helper | Share cleanup logic outside dependency body | |
| Route-level only | Let routes handle post-failure cleanup | |

**User's choice:** Inside `require_auth`
**Notes:** The dependency should own the invalid-session cleanup behavior directly.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| None; trust persisted auth record | Match today's vault-trust model | ✓ |
| Minimal sanity checks | Add lightweight validation | |
| Revalidate with Jellyfin each request | Strongest live validation | |

**User's choice:** None; trust the persisted auth record
**Notes:** The user preserved the current no-per-request-Jellyfin-validation rule.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Keep exact current `401` contract | Preserve status and detail string exactly | ✓ |
| Same `401`, more specific stale-session detail | Minor contract refinement | |
| Distinct auth error variants | New failure taxonomy | |

**User's choice:** Keep exact current `401` contract
**Notes:** The external failure contract should remain unchanged.

---

## Cleanup and invalid-session handling

### Question 1

| Option | Description | Selected |
|--------|-------------|----------|
| Auth service only | Service owns cleanup orchestration directly | ✓ |
| Auth repository only | Cleanup belongs purely to persistence layer | |
| Service through repository | Service delegates cleanup into repository operations | |

**User's choice:** Auth service only
**Notes:** The user wanted cleanup to live at the service layer rather than become a standalone repository concern.

### Question 2

| Option | Description | Selected |
|--------|-------------|----------|
| Swallow and log | Logout remains successful from the caller's perspective | ✓ |
| Surface a 500 | Caller sees cleanup failure | |
| Retry synchronously before returning | Block on cleanup reliability | |

**User's choice:** Swallow and log
**Notes:** Best-effort cleanup failure should not break the user-visible logout path.

### Question 3

| Option | Description | Selected |
|--------|-------------|----------|
| No new background cleanup | Keep behavior request-driven | ✓ |
| Add explicit periodic cleanup hook | Introduce scheduled behavior now | |
| Only if Phase 37 bootstrap already provides a natural place | Conditional background path | |

**User's choice:** No new background cleanup
**Notes:** Request-driven cleanup remains sufficient for this phase.

### Question 4

| Option | Description | Selected |
|--------|-------------|----------|
| Assert only visible auth semantics | Keep tests black-box only | |
| Assert semantics and cleanup invocation | Heavier route-level verification | |
| Focus cleanup verification in repository/service unit tests | Keep route tests lighter | ✓ |

**User's choice:** Focus cleanup verification in repository/service unit tests
**Notes:** The user wanted cleanup coverage, but not by making route tests carry all the burden.

---

## the agent's Discretion

None.

## Deferred Ideas

None.
