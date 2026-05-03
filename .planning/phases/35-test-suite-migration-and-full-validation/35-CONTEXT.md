# Phase 35: Test Suite Migration and Full Validation - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate all 18 test files (324 tests) from Flask test client patterns to FastAPI `TestClient` so the full suite passes against the FastAPI app built in Phases 30–34. This includes replacing `app.test_client()`, `session_transaction()`, `response.get_json()`, and `response.data` with their FastAPI/requests equivalents. The `create_app()` factory also gets a `SECRET_KEY` override so tests are fully self-contained.

**In scope:**
- Replace `app.test_client()` with `TestClient(app)` in `conftest.py`
- Add `app.dependency_overrides[require_auth]` support in the `app`/`client` fixtures
- Write a `set_session_cookie(client, data, secret_key)` helper using `itsdangerous` for session state injection
- Update `create_app()` to accept `SECRET_KEY` from `test_config` (passed to `SessionMiddleware`)
- Replace `response.get_json()` → `response.json()` (34 occurrences)
- Replace `response.data` → `response.content` (15 occurrences)
- Replace all 20 `session_transaction()` call sites
- Update REQUIREMENTS.md TST-01 to reflect actual test count (324, not 48)
- Verify `docker build` succeeds and container starts with Uvicorn CMD (success criterion 4)

**Out of scope:**
- Pydantic request/response models (v2.1 — ARCH-02)
- Any behavioral changes to route handlers
- New tests beyond migrating existing ones

</domain>

<decisions>
## Implementation Decisions

### Auth Injection Strategy (mixed)

- **D-01:** Most tests use `app.dependency_overrides[require_auth]` to bypass auth entirely. The `app` fixture adds this override by default; `client` fixture builds a `TestClient` from it. Teardown clears `app.dependency_overrides` after each test (no override state leaks — success criterion 3).
- **D-02:** `test_routes_auth.py` and `test_route_authorization.py` explicitly opt OUT of the `require_auth` override by using a separate `app_real_auth` / `client_real_auth` fixture variant that does NOT set `dependency_overrides[require_auth]`. These tests exercise the real auth code path.
- **D-03:** The default `AuthUser` injected by the override is `AuthUser(jf_token="valid-token", user_id="verified-user")` — matching the `FakeProvider` user identity used throughout existing tests. Tests that need a different user identity can parameterize the override inline.

### Session State Injection (cookie crafting)

- **D-04:** Application session state (`active_room`, `solo_mode`, `my_user_id`, `jf_delegate_server_identity`, etc.) is injected via a `set_session_cookie(client, data, secret_key)` helper in `conftest.py`. The helper uses `itsdangerous.TimestampSigner` (Starlette's `SessionMiddleware` uses this under the hood with the `FLASK_SECRET` key) to produce a valid signed session cookie and sets it on the `TestClient`'s `cookies` dict.
- **D-05:** The `_set_session` / `_set_session_room` local helpers in individual test files are replaced with calls to `set_session_cookie()`. Auth setup (seeding `user_tokens`, setting `session_id`) is dropped — auth is handled by the `dependency_overrides` from D-01 instead.
- **D-06:** For tests that currently set ONLY auth-related session keys (just `session_id`), the override from D-01 is sufficient — no cookie crafting needed. Only tests that also need `active_room`, `solo_mode`, or similar app state call `set_session_cookie()`.

### create_app SECRET_KEY injection

- **D-07:** Update `create_app()` to read `SECRET_KEY` from `test_config` and pass it to `SessionMiddleware` instead of always reading `os.environ["FLASK_SECRET"]`. The `app` fixture passes `SECRET_KEY` matching the `FLASK_SECRET` env var already set in conftest — so the signing key used by `set_session_cookie()` and the key used by the live app are guaranteed to match.
- **D-08:** The `global app` at module level (`app = create_app()`) continues to use `os.environ["FLASK_SECRET"]`. Only the test-created instances get `SECRET_KEY` from test_config.

### Mechanical Replacements

- **D-09:** `response.get_json()` → `response.json()` across all 34 occurrences. FastAPI's `TestClient` wraps `requests.Response`, which uses `.json()`.
- **D-10:** `response.data` → `response.content` (bytes) across all 15 occurrences. If any test decodes to string, use `response.text` instead.
- **D-11:** `app.test_client()` → `TestClient(app, raise_server_exceptions=False)` for error-handling tests that expect 4xx/5xx without exceptions being raised; `TestClient(app)` for the rest.

### Documentation Update

- **D-12:** Update `REQUIREMENTS.md` TST-01 to reflect the actual test count (324 tests, not 48). The "no modifications to test logic" constraint still applies — only API surface changes are allowed.

### Claude's Discretion

- Exact Starlette session cookie format: planner should verify the `itsdangerous` signer variant Starlette 0.46+ uses (likely `URLSafeTimedSerializer` with a `cookiesession` salt) before writing the helper — the signing format must match exactly or cookies will be rejected.
- `raise_server_exceptions` flag: planner decides per-test-file whether it's needed; apply it surgically to error-handling test files only.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and Roadmap
- `.planning/REQUIREMENTS.md` — TST-01: "All tests updated to use FastAPI's TestClient; full test suite passes with no modifications to test logic (only API surface changes)"
- `.planning/ROADMAP.md` §Phase 35 — 4 success criteria: all tests pass, no Flask patterns remain, no override state leaks, Docker starts with Uvicorn

### App Factory and Auth Layer
- `jellyswipe/__init__.py` §`create_app()` — current factory; `SECRET_KEY` from `test_config` override goes here (D-07)
- `jellyswipe/dependencies.py` — `require_auth`, `AuthUser`, `get_provider` — these are the dependencies to override in tests
- `jellyswipe/auth.py` — `get_current_token(session)` — what `require_auth` calls; real auth tests go through this path

### Existing Test Infrastructure (source to migrate)
- `tests/conftest.py` — current `app`/`client` fixtures; `FakeProvider`; `_set_session`-style helpers; all change in this phase
- `tests/test_routes_room.py` — `_set_session()` helper (20-line auth+session setup); highest density of `session_transaction()` calls
- `tests/test_routes_sse.py` — `_set_session_room()` helper; SSE stream tests
- `tests/test_routes_auth.py` — must use `client_real_auth` (not overridden) per D-02
- `tests/test_route_authorization.py` — must use `client_real_auth` (not overridden) per D-02
- `tests/test_routes_xss.py` — 7 `session_transaction()` calls; most complex migration
- `tests/test_error_handling.py` — uses `raise_server_exceptions=False` pattern per D-11

### Prior Phase Context
- `.planning/phases/34-sse-route-migration/34-CONTEXT.md` — D-05 to D-11: the auth and session approach that tests are migrating to
- `.planning/phases/32-auth-rewrite-and-dependency-injection-layer/32-CONTEXT.md` — D-01 to D-05: `AuthUser`, `require_auth()` contract
- `.planning/phases/33-router-extraction-and-endpoint-parity/33-CONTEXT.md` — router structure all tests exercise

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jellyswipe/dependencies.py` exports `require_auth`, `AuthUser`, `get_provider` — all override targets for tests
- `tests/conftest.py` `FakeProvider` class — keep as-is; override `get_provider` dependency to return it
- `tests/conftest.py` `db_connection` / `db_path` fixtures — already framework-agnostic; no change needed
- `tests/conftest.py` `mock_env_vars` fixture — already framework-agnostic; no change needed
- `fastapi.testclient.TestClient` — wraps `requests.Session`; cookies persist between calls within the same client instance

### Established Patterns
- `app.dependency_overrides[require_auth] = lambda: AuthUser(...)` — standard FastAPI test pattern; must be cleared in fixture teardown
- `app.dependency_overrides[get_provider] = lambda: FakeProvider()` — replaces `monkeypatch.setattr(jellyswipe_module, "_provider_singleton", ...)` from current conftest
- `itsdangerous.URLSafeTimedSerializer` — Starlette's session middleware uses this; planner must verify the exact salt and serializer variant before implementing `set_session_cookie()`

### Integration Points
- `create_app(test_config={"DB_PATH": ..., "SECRET_KEY": ..., "TESTING": True})` — the `SECRET_KEY` key must be wired to `SessionMiddleware(secret_key=...)` inside the factory
- `TestClient` created **inside** the `app` fixture or the `client` fixture — NOT at module level — so `dependency_overrides` are set before the client is constructed and cleared after
- Rate limiter: `_rl.reset()` call in current `app` fixture must be preserved; `rate_limiter` import stays

</code_context>

<specifics>
## Specific Ideas

- The `set_session_cookie()` helper should accept an arbitrary dict and a secret key string, produce a cookie value string, and set it via `client.cookies.set("session", cookie_value)` before the test makes its request.
- Planner should verify: does Starlette 0.36+ use `"session"` as the cookie name? (It does by default.) Does it use `URLSafeTimedSerializer` with salt `"starlette.sessions"`? This is the key research item.
- Tests that previously called both `_set_session()` (auth) and direct DB seeding (rooms, swipes) should keep the DB seeding and replace `_set_session()` with: (a) auth via dependency_override (already in fixture), and (b) `set_session_cookie()` for `active_room` if needed.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 35-Test Suite Migration and Full Validation*
*Context gathered: 2026-05-03*
