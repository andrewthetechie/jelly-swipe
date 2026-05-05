# Retrospective — Jelly Swipe

Cross-milestone trends accumulate at the bottom of this file.

---

## Milestone: v1.0 — Jellyfin support

**Shipped:** 2026-04-24  
**Phases:** 1–9 | **Theme:** Either/or Plex/Jellyfin backend with verification closure and operator E2E narrative.

### What was built

- Provider abstraction with Jellyfin REST client, env auth, deck/genre/proxy/TMDB parity routes.
- Verification and validation artifacts for configuration through user parity (`01`–`05`, `06`–`07`, `08`).
- Phase 9: Flask session delegate identity for Jellyfin browser UX + poster letterboxing in dual HTML surfaces.

### What worked

- Phased verification closure (6–7) separated “evidence debt” from feature delivery.
- Either-or deployment model kept configuration and security review tractable.

### What was inefficient

- `gsd-sdk query milestone.complete` failed in this environment (`version required for phases archive`); milestone close was finished manually with the same artifacts the CLI would have produced.

### Patterns established

- Native per-phase `*-VERIFICATION.md` plus milestone audit file for re-audit readiness.
- Mirrored `templates/index.html` and `data/index.html` for PWA-facing changes.

### Key lessons

- Ship UI polish (Phase 9) after auth/library parity so delegate flows sit on a stable provider stack.
- Keep Plex parity (ARC-02) on the checklist until operator matrix in `02-VERIFICATION.md` is fully green.

### Cost observations

Not tracked in-repo; add session/token notes here if you adopt cost logging next milestone.

---

## Milestone: v1.1 — Jelly Swipe rename

**Shipped:** 2026-04-24  
**Phases:** (none under `.planning/phases/`) | **Theme:** Maintainer identity, Docker/DB defaults, UI/PWA strings, LICENSE/README fork policy.

### What was built

- End-to-end rename in `app.py`, HTML surfaces, manifests, compose, Docker Hub workflow, Unraid template, LICENSE, README, and planning mirrors.
- GHCR release workflow on GitHub **Release** (`release-ghcr.yml`).

### What worked

- Tight scope (BRAND-01–04) shipped without spinning new phase directories.

### What was inefficient

- `gsd-sdk query milestone.complete` still unusable for this repo; manual milestone archives duplicate CLI intent.

### Patterns established

- Single upstream fork line in README/LICENSE; AndrewTheTechie everywhere else in packaging.

### Key lessons

- Document Plex client id change for operators (re-pin) alongside DB filename migration.

### Cost observations

Not tracked in-repo.

---

## Milestone: v1.5 — Route Test Coverage

**Shipped:** 2026-04-26  
**Phases:** 21–29 | **Plans:** 9 | **Theme:** Factory pattern refactor, comprehensive route tests (159 total), XSS defense, CSP compliance.

### What was built

- Flask app factory pattern (`create_app(test_config=None)`) enabling isolated test instances.
- Shared test infrastructure: FakeProvider mock, function-scoped app/client fixtures.
- 5 route test files: auth (14 tests), XSS (13), room (27), proxy (16), SSE (8).
- `_XSSSafeJSONProvider` for global OWASP JSON XSS defense.
- External CSS/JS + self-hosted font for CSP `default-src 'self'` compliance.
- 70% coverage threshold enforced in CI (`--cov-fail-under=70`).

### What worked

- Factory pattern enabled clean test isolation — each test gets fresh app instance with temp DB.
- Phased approach (infrastructure first, then test files by route category) kept each phase focused.
- Shared FakeProvider in conftest.py avoided duplication across all route test phases.
- Counter-based `time.time` mock solved SSE streaming test reliability without real delays.

### What was inefficient

- Phase 24 discovered Flask 2.3.3 `jsonify()` does NOT auto-escape HTML — CONTEXT.md was wrong. Required implementing `_XSSSafeJSONProvider` mid-phase (deviation from plan).
- Phase 29 font URL in plan was outdated (v18 → v23), required auto-fix during execution.

### Patterns established

- `_XSSSafeJSONProvider` pattern: global JSON response sanitization as security layer.
- SSE test pattern: monkeypatch `time.sleep`/`time.time` with counter-based mock for loop control.
- External static files pattern: CSS classes + data-attributes instead of inline styles/handlers.

### Key lessons

- Verify framework assumptions (e.g., Flask auto-escaping) before planning — CONTEXT.md errors propagate into plan deviations.
- Test infrastructure phases (Phase 22) pay for themselves immediately across all subsequent phases.
- Coverage enforcement should be one of the last phases — let tests accumulate naturally, then set threshold.

### Cost observations

- 9 phases completed in ~30 minutes of execution time.
- 53 commits in milestone range.
- Most phases completed in 1-6 minutes each.

---

## Milestone: v2.0 — Flask → FastAPI + MVC Refactor

**Shipped:** 2026-05-05
**Phases:** 30–35 | **Plans:** 13 | **Theme:** Framework migration, router split, async SSE, and FastAPI test migration.

### What was built

- FastAPI/Uvicorn runtime stack with Docker CMD updated from Gunicorn/gevent.
- Thin FastAPI app factory plus domain routers for auth, rooms, media, proxy, and static files.
- Shared dependency layer for auth, DB connections, provider access, and rate limiting.
- Async SSE route with non-blocking sleeps and connection cleanup.
- FastAPI `TestClient` suite with final post-PR verification at 328 passing tests.

### What worked

- Infrastructure-first ordering kept later router/test work unblocked.
- Real-auth route tests caught session-cookie and vault-path regressions.
- Nyquist validation passes after implementation found gaps that regular summaries missed.

### What was inefficient

- The pre-close milestone audit became stale after later validation and PR fixes, so it had to be archived as historical evidence rather than treated as final truth.
- Some generated accomplishment extraction pulled noisy SUMMARY text into `MILESTONES.md`, requiring manual cleanup.
- Provider access is still partly direct-call based, which keeps some dependency override patterns less pure than ideal.

### Patterns established

- FastAPI app factory plus domain-router split for all HTTP surfaces.
- Starlette signed-session cookie helper for test session injection.
- Browser `session_id` as the room participant identity when matching two browser sessions that share a Jellyfin user.

### Key lessons

1. Treat browser session identity separately from Jellyfin account identity in collaborative room flows.
2. Re-run or supersede milestone audits after late validation/fix commits; otherwise the archived audit is only a historical snapshot.
3. Route-level real-auth tests are worth keeping even when dependency overrides make unit tests easier.

### Cost observations

- Cost tracking is not recorded in-repo.
- High rework areas were test migration and post-PR behavioral fixes, not the basic framework swap.

---

## Cross-Milestone Trends

| Milestone | Verification style | Open parity gaps |
|-----------|---------------------|------------------|
| v1.0 | Native phase VERIFICATION + VALIDATION + audit | ARC-02 (Plex), partial J\* traceability rows |
| v1.1 | Requirements checklist + in-tree review (no phase VERIFICATION dirs) | Same v1.0 parity gaps unchanged |
| v1.5 | SUMMARY.md per phase + `audit-open` clear | None — all requirements validated |
| v2.0 | SUMMARY + validation artifacts + archived milestone audit + full suite | Pydantic models and provider DI purity deferred |
