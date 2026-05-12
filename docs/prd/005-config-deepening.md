## Problem Statement

The current configuration and database URL resolution path is shallow and scattered. Answering "give me the Jellyfin URL" or "where is the SQLite file" requires navigating import-time side effects in `config.py`, a mutable global holder in `db_paths.py`, a five-source fallback chain in `migrations.py`, four `RUNTIME_*` module-level variables in `db_runtime.py`, and defensive lazy-import lock-juggling in `dependencies.py`.

From the developer's perspective, this creates three concrete problems:

- **Testability is blocked at import time.** Importing `config.py` triggers `load_dotenv()`, validates all env vars, and performs SSRF DNS resolution. Tests and tooling cannot import any module that transitively touches `config.py` without a fully populated `.env` file.
- **Database URL resolution has no locality.** The question "which SQLite file am I using" is answered by five functions across four files (`db_paths.py`, `migrations.py`, `db_runtime.py`, `db.py`), plus a mutable `ApplicationDbPath` holder that `__init__.py` sets at import time to the same value an env var already holds. Bugs in path resolution can appear in any of these files.
- **Runtime lifecycle state is tangled into config.** The provider singleton, token-user-ID cache, and async engine globals live alongside env-var constants, making it unclear what is inert configuration and what is mutable runtime state.

The app needs a single deep config module that holds all inert configuration behind a small, validated, immutable interface — and nothing else.

## Solution

Replace the current `config.py` / `db_paths.py` / multi-file DB URL resolution with a single **`AppConfig`** model built on `pydantic-settings.BaseSettings`. This module will own env-var reading, validation (including SSRF protection on `jellyfin_url`), and derived database URL computation. It will have no import-time side effects, hold no mutable runtime state, and be constructed once during application bootstrap.

Runtime lifecycle concerns (provider singleton, async engine, token cache) will be scattered to the modules that own those behaviors. The mutable `ApplicationDbPath` holder and the five-source DB path fallback chain will be deleted. Alembic will use its own minimal env-var resolution path, documented and independent of `AppConfig`.

Configuration will flow through the codebase via FastAPI dependency injection. A `get_config` dependency will return the cached `AppConfig` instance from `app.state`. Tests will construct `AppConfig(...)` directly with explicit values, bypassing env vars entirely.

## User Stories

1. As a developer, I want to import any module in the codebase without triggering env-var validation or network calls, so that tests and tooling work without a production `.env` file.
2. As a developer, I want one place to look for all application configuration values, so that I do not need to trace through five files to answer "what database am I connected to."
3. As a developer, I want configuration to be immutable after construction, so that runtime code cannot silently mutate config values and create hard-to-trace bugs.
4. As a developer, I want Pydantic to handle env-var reading and validation, so that the codebase does not maintain a hand-rolled validation engine.
5. As a developer, I want SSRF validation on the Jellyfin URL to happen as a Pydantic field validator, so that validation rules live with the data they protect.
6. As a developer, I want database URL derivation (sync and async forms) to be computed properties on the config object, so that URL construction logic is concentrated in one place.
7. As a developer, I want the config object injected via FastAPI `Depends()`, so that route handlers and services receive config through the same pattern as other dependencies.
8. As a developer, I want tests to construct config with explicit values, so that test isolation does not depend on env-var manipulation or mutable globals.
9. As a developer, I want the provider singleton, token cache, and async engine to live in the modules that own their lifecycle, so that config stays inert and those modules stay deep.
10. As a developer, I want Alembic to resolve its database URL independently of `AppConfig`, so that migration tooling does not import the application.
11. As an operator, I want the `TOKEN_USER_ID_CACHE_TTL_SECONDS` to be tunable via environment variable, so that I can adjust cache behavior without code changes.
12. As a future maintainer, I want the config module to be the test surface for configuration concerns, so that I can verify env-var mapping, defaults, and validation through the `AppConfig` interface directly.

## Implementation Decisions

### New module shape

- `config.py` will contain `AppConfig(BaseSettings)` and nothing else.
- Fields: `jellyfin_url` (str, required), `jellyfin_api_key` (str, required), `tmdb_access_token` (str, required), `flask_secret` (str, required), `db_path` (str, optional with default resolving to `data/jellyswipe.db`), `token_user_id_cache_ttl_seconds` (int, default 300).
- Computed properties: `sync_db_url`, `async_db_url`.
- A `@field_validator` on `jellyfin_url` will call `validate_jellyfin_url()` from `ssrf_validator.py`.
- `model_config` will set `env_file = ".env"` so that `pydantic-settings` handles dotenv loading.
- The model will be frozen (immutable after construction).

### Deleted entirely

- `db_paths.py` — the `ApplicationDbPath` mutable holder and `default_database_file_path()` are subsumed by `AppConfig.db_path` with its default.
- The five-source fallback chain in `migrations.py` `get_database_url()` — replaced by `AppConfig.sync_db_url` for application use.
- `RUNTIME_DATABASE_URL_OVERRIDE` in `db_runtime.py` — tests inject their own `AppConfig` instead.

### Scattered to rightful owners

| Current resident of `config.py` | New home | Rationale |
|---|---|---|
| `TMDB_AUTH_HEADERS` | `tmdb.py` (module-local, derived from config) | Implementation detail of the TMDB client |
| `CLIENT_ID` | `jellyfin_library.py` (module-local constant) | Implementation detail of the Jellyfin client |
| `IDENTITY_ALIAS_HEADERS` | `auth.py` (module-local constant) | Only consumed by auth logic |
| `_token_user_id_cache` + TTL | `auth.py` (runtime state) | Mutable cache, not inert config; TTL value comes from injected `AppConfig` |
| `_provider_singleton` | `dependencies.py` (consolidated) | Runtime lifecycle, not config; lock-juggling simplified to one location |

### Dependency injection

- `bootstrap.py` (or the lifespan handler) constructs `AppConfig()` once and stores it on `app.state.config`.
- A `get_config` FastAPI dependency reads `request.app.state.config` and returns the cached instance. No re-validation, no re-parsing — one frozen object for the lifetime of the process.
- Services that need config values receive `AppConfig` as a parameter (via the dependency chain or direct pass-through).
- Tests construct `AppConfig(jellyfin_url="http://test", jellyfin_api_key="fake", ...)` directly, bypassing env vars and dotenv entirely.

### `db_runtime.py` changes

- `initialize_runtime` will accept a URL string (from `AppConfig.async_db_url`) instead of reaching into module-level globals or fallback chains.
- `RUNTIME_DATABASE_URL_OVERRIDE` will be deleted. Test overrides flow through `AppConfig` construction.
- The module continues to own async engine and sessionmaker lifecycle — that responsibility does not move.

### Alembic independence

- Alembic's `env.py` will use its own minimal resolution function (~3 lines): read `DATABASE_URL` env var → read `DB_PATH` env var and build a SQLite URL → fall back to `data/jellyswipe.db`.
- This function will be documented with a comment explaining why it does not go through `AppConfig` (Alembic must not import the application).
- `migrations.py` retains `upgrade_to_head()` and `_alembic_config()`, but `get_database_url()` is replaced or simplified to delegate to `AppConfig` when called from application code, or to the Alembic-local resolution when called from migration tooling.

### New dependency

- `pydantic-settings` will be added to `pyproject.toml` dependencies.

## Testing Decisions

- `AppConfig` construction with valid env vars should produce correct field values and derived URLs.
- `AppConfig` construction with missing required fields should raise `ValidationError`.
- `AppConfig` construction with a malicious `jellyfin_url` should fail SSRF validation.
- `AppConfig.sync_db_url` and `async_db_url` should produce correct SQLite URL forms from `db_path`.
- `AppConfig.db_path` should resolve to the default when not provided.
- `AppConfig` should be frozen — attribute assignment after construction should raise.
- The `get_config` dependency should return the same instance across multiple calls within a request.
- Tests should construct `AppConfig(...)` with explicit values without needing env vars or a `.env` file.
- Alembic's independent resolution should produce the same URL as `AppConfig` given the same env vars.
- Modules that previously imported constants from `config.py` (TMDB headers, identity headers, client ID) should continue to work after the scatter, sourcing values from their new locations.

## Out of Scope

- Multi-database-engine support. The codebase is SQLite-only; if that changes, config will be re-engineered.
- Reworking the provider singleton lifecycle beyond consolidating it into `dependencies.py`.
- Reworking the async engine/sessionmaker lifecycle beyond making `initialize_runtime` accept a URL parameter.
- Introducing a generic application-wide dependency container or service locator.
- Changing how `bootstrap.py` starts uvicorn or runs migrations, beyond passing `AppConfig` to `initialize_runtime`.
- Refactoring `db.py` maintenance functions — those are a separate deepening candidate.

## Further Notes

- This PRD is about **deleting indirection**, not adding abstraction. The success condition is that a developer can read `config.py`, see five fields with validators, and know everything about how the app is configured — without chasing through `db_paths.py`, `migrations.py`, `db_runtime.py`, and `__init__.py`.
- The `pydantic-settings` dependency is justified because it replaces hand-rolled env-var parsing, dotenv loading, and validation with a single well-maintained library that the codebase already depends on transitively (via Pydantic).
- The combined effect of this change and the existing Session Match Mutation PRD is that two of the three deepest friction areas in the codebase (config scatter and mutation locality) will have clear ownership behind deep interfaces.

