## Problem Statement

The current Session Match mutation path is technically correct in the narrow sense that it can persist Swipes and create Matches, but its architecture is shallow and hard to extend safely. The rules for applying a Swipe, advancing a participant cursor, detecting a counterparty, creating Match rows, and appending Session events are spread across route code, a transaction-script-style mutation service, raw SQL helpers, generic repositories, and the Session Event Stream contract.

From the user’s perspective, this creates fragility around the most important live Session behavior:

- Hosted Sessions depend on a concurrency-sensitive mutation path that is hard to reason about and easy to regress.
- Undo and Match deletion do not communicate their real effect clearly, which makes client behavior rely on assumptions rather than explicit Session outcomes.
- The router still knows too much about Session mutation details, which raises the chance of future drift between transport behavior and Session rules.

The app needs a deeper Session Match Mutation module that makes Session behavior explicit at its interface while hiding transaction serialization, table coordination, and event persistence details behind a single seam.

## Solution

Replace the current `SwipeMatchService` shape with a deeper **Session Match Mutation** module. This module will own the Session-side mutation rules for `apply Swipe`, `undo Swipe`, and `delete Match` through a command-oriented interface that returns explicit domain results.

The module will accept a **Session actor** rather than raw web-session plumbing, will keep cursor advancement inside the atomic Session mutation, and will decide when a Match was created or removed from Session state. It will prefer SQLAlchemy and keep lower-level SQLite-specific logic limited to one internal serialized adapter used where truly necessary for the concurrency-critical `apply Swipe` command.

The module will not own post-commit notifier wakeups and will not own external catalog lookup. It will delegate Session Event Ledger shaping to the Session Event Ledger module while still deciding which user-visible domain outcomes should produce events.

## User Stories

1. As a Session participant, I want a Swipe to be applied through one authoritative Session mutation path, so that Match behavior is consistent under concurrent use.
2. As a Session participant, I want my Swipe to advance my place in the Session deck atomically, so that I do not see inconsistent card position after a successful command.
3. As a Session participant in a hosted Session, I want mutual right-swipes to become Matches reliably, so that the app behaves correctly when both people swipe around the same time.
4. As a Session participant in Solo mode, I want my right-swipe to create a Match through the same mutation seam, so that solo and hosted behavior stay coherent.
5. As a Session participant, I want the app to know whether a Swipe created a Match, so that Session behavior is explicit rather than inferred from side effects.
6. As a Session participant, I want `undo Swipe` to tell me whether anything was actually undone, so that the client can react to real Session outcomes instead of guessing.
7. As a Session participant, I want `delete Match` to tell me whether anything was actually deleted, so that Match history behavior is explicit.
8. As a Session participant, I want failed Session mutations like a missing Session or missing target Swipe to surface as clear outcomes, so that the UI can distinguish errors from no-ops.
9. As a Session host, I want the router layer to translate domain outcomes into HTTP responses, so that transport behavior stays separate from Session rules.
10. As a developer, I want Session Match mutation behavior concentrated behind one seam, so that I can change Session rules without editing route code, repositories, and raw SQL helpers in several places.
11. As a developer, I want `apply Swipe`, `undo Swipe`, and `delete Match` to live in one module, so that Match-related rules do not fragment into shallow sidecar modules.
12. As a developer, I want the module interface to be command-oriented, so that callers do not need to know persistence ordering, table participation, or locking rules.
13. As a developer, I want the mutation seam to accept a Session actor instead of raw `request.session`, so that web-session storage details do not leak into Session logic.
14. As a developer, I want cursor advancement to stay inside the Session Match Mutation seam, so that callers do not need to coordinate multiple state changes manually.
15. As a developer, I want Match creation to append the right Session Event Ledger events without leaking wire-shape knowledge into the mutation module, so that the Session Event Stream contract stays deep too.
16. As a developer, I want post-commit notifier wakeups to stay outside the Session Match Mutation seam, so that transport optimization remains separate from domain mutation.
17. As a developer, I want the module to prefer SQLAlchemy, so that the codebase uses one dominant persistence style instead of drifting further into ad hoc raw SQL.
18. As a developer, I want lower-level SQL to be limited to the serialized SQLite adapter where truly necessary, so that SQLite-specific complexity stays localized.
19. As a developer, I want only the concurrency-critical `apply Swipe` command to require serialized SQLite behavior initially, so that the seam stays simple where ordinary SQLAlchemy paths are sufficient.
20. As a developer, I want `undo Swipe` and `delete Match` to remain behind the same Session Match Mutation seam even if they use simpler persistence paths, so that the interface stays coherent.
21. As a developer, I want the module to derive as much metadata as possible from existing Session state, so that callers provide only the minimal external catalog facts needed.
22. As a developer, I want external catalog lookup to stay outside the mutation seam, so that Jellyfin availability and Session correctness remain separate concerns.
23. As a developer, I want the deep module to return explicit domain results for all three commands, so that tests can assert behavior directly rather than inspecting incidental side effects.
24. As a developer, I want a clean cutover away from `SwipeMatchService`, so that there is no ambiguity about where Session Match rules live.
25. As a future maintainer, I want the interface to be the test surface, so that I can confidently refactor the implementation without rewriting route-level assumptions.

## Implementation Decisions

- Replace the current Session Match mutation service with a new deep module named **Session Match Mutation**.
- The module will expose three explicit commands: `apply Swipe`, `undo Swipe`, and `delete Match`.
- The interface will be command-oriented, not repository-oriented.
- The interface will return explicit domain results for all commands rather than route-shaped `(body, status)` pairs or sentinel values like `None`.
- The module will accept a **Session actor** carrying domain-relevant participant identity and browser-session discrimination, instead of raw session-dictionary plumbing.
- The module will own cursor advancement as part of the atomic Session mutation.
- The module will decide when a Match is created as a result of a Swipe and will report that in its domain result.
- The module will keep notifier wakeups outside the seam; the application layer remains responsible for waking live subscribers after commit.
- The module will not own Jellyfin or external catalog metadata resolution.
- Callers will provide only the minimal external catalog facts the module cannot derive from Session state.
- The module will derive as much Match metadata as possible from Session state already persisted in the Session deck.
- The module will decide that a `match_found` event should exist, but the Session Event Ledger module will own the event envelope and payload shaping.
- `undo Swipe` will be modeled as a strict Session command with explicit outcomes, not as a silent best-effort reversal.
- `delete Match` will remain inside the same module for now, even though it behaves more like Match-history mutation than live Session mutation.
- Match removal from `undo Swipe` or `delete Match` will remain invisible to the Session Event Stream for now; no new “match_removed” event will be introduced in this change.
- The implementation will prefer SQLAlchemy as the default persistence style.
- One internal SQLite-specific serialized adapter is allowed as part of the implementation, because the concurrency-critical `apply Swipe` path requires strict serialization for Session correctness.
- Lower-level SQL should be used only where SQLAlchemy alone does not provide a clean way to preserve the serialized Session mutation semantics.
- Initially, only `apply Swipe` should use the serialized SQLite adapter.
- `undo Swipe` and `delete Match` should remain on ordinary SQLAlchemy paths unless a concrete race demonstrates the need for stronger serialization.
- The module should be introduced as a clean cutover, replacing the old `SwipeMatchService` outright rather than coexisting with it.
- The router layer will translate domain results into HTTP responses and preserve current transport responsibilities like request parsing, auth dependency use, and post-commit live notification.
- The change should preserve the existing Session Event Stream direction: domain mutations persist Session events transactionally, and live delivery remains a post-commit concern.

## Testing Decisions

- Good tests should verify external behavior at the module seam, not internal helper structure. The important assertions are command outcomes, Session state changes, Match creation/removal behavior, cursor advancement, event persistence side effects, and transport translation at the router layer.
- The primary deep-module tests should target the new Session Match Mutation interface directly.
- `apply Swipe` tests should cover left-swipes, solo right-swipes, hosted right-swipes without a counterparty, hosted mutual right-swipes, missing Session outcomes, cursor advancement, and correct Session event emission decisions.
- `undo Swipe` tests should cover changed vs no-op outcomes, Swipe removal, Match removal for the caller when applicable, and lack of Session Event Stream widening.
- `delete Match` tests should cover changed vs no-op outcomes and confirm the command stays a Match-history mutation rather than a live Session event source.
- Router tests should verify translation of domain results into HTTP responses and verify that notifier wakeups still happen only after successful commit.
- Tests should verify that the Session actor interface hides raw web-session storage details from the module test surface.
- Tests should verify that the module continues to derive Match metadata correctly from Session state plus minimal external facts.
- Tests should verify that Session Event Ledger collaboration is behaviorally correct without coupling to exact internal helper composition.
- Prior art already exists in the codebase in the current swipe/match service tests, route-level room tests, Session Event Ledger tests, and Session Event Stream tests. Those should guide fixture style and behavior coverage, but the new tests should shift emphasis from implementation detail to command-oriented outcomes.

## Out of Scope

- Reworking the Session Event Stream architecture itself beyond preserving the current ledger-based direction.
- Introducing a live “match_removed” or similar negative event into the Session Event Stream.
- Moving Jellyfin metadata resolution into the Session Match Mutation module.
- Changing how Match history is presented in the UI.
- Redesigning Session deck construction, filtering, or bootstrap behavior.
- Multi-process or multi-instance coordination beyond the current single-process assumptions.
- A generic command bus or broader application-wide mutation framework.
- Refactoring unrelated Room lifecycle logic that does not belong to Match mutation.

## Further Notes

- This PRD is intentionally about **deepening one seam**, not about broad rewrite-for-rewrite’s-sake. The success condition is that Session Match rules become easier to understand, easier to test, and harder to accidentally split apart again.
- The most important architectural discipline is keeping the interface narrow while allowing the implementation to remain honest about SQLite concurrency constraints.
- The Session Match Mutation module and the Session Event Ledger module should become complementary deep modules: one decides Session mutation outcomes, the other owns replayable event persistence and framing.

