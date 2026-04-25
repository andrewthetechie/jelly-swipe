# Milestones — Jelly Swipe

Living log of shipped versions. For current planning, see `.planning/ROADMAP.md`.

---

## v1.3 — Unit Tests

**Shipped:** 2026-04-25
**Theme:** Framework-agnostic pytest test suite with 48 tests for database and Jellyfin provider modules, plus CI workflow for automated testing
**Phases:** 14–17 (infrastructure 14, database 15, Jellyfin 16, coverage/CI 17)

**Archives:**

- [v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md) — full phase roadmap snapshot
- [v1.3-REQUIREMENTS.md](milestones/v1.3-REQUIREMENTS.md) — INFRA/DB/API/COV requirements at close (12/12 complete)

**Deliverables (high level):** 48 tests (15 infrastructure + 17 database + 29 Jellyfin provider) with 100% requirement coverage; pytest-cov terminal output; GitHub Actions test workflow running on every push/PR; function-scoped fixtures for test isolation; mocked HTTP requests to prevent external API calls.

**Stats:** 4 phases, 9 plans, 19 tasks, 48 tests, 27 files changed, 4,096 insertions, 2 deletions, ~1 hour execution time

**Key accomplishments:**
1. pytest Testing Framework Setup — Installed pytest 9.0.3, pytest-cov, pytest-mock, responses, pytest-timeout; configured test discovery and output; generated frozen uv.lock
2. Framework-Agnostic Test Infrastructure — Created conftest.py with environment fixtures and monkeypatching to import modules directly without Flask app initialization
3. Database Module Testing — Created 17 tests for db.py with tmp_path fixture, function-scoped isolation, and 87% coverage
4. Jellyfin Provider Testing — Created 29 tests for jellyfin_library.py covering auth, token caching, user ID resolution, library discovery, genres, deck fetching, and TMDB resolution
5. Coverage & CI Integration — Configured pytest-cov for terminal output and created GitHub Actions workflow running 48 tests on every push/PR

**Known gaps at close:** None — all requirements validated

**Deferred items at milestone close:** `gsd-tools.cjs audit-open` reported **all artifact types clear** (no blocking open debug/UAT items)

---

## v1.2 — uv + Package Layout + Plex Removal

**Shipped:** 2026-04-25
**Theme:** Migrate to uv dependency management, refactor to jellyswipe/ package layout, remove all Plex support to make application Jellyfin-only
**Phases:** 10–13 (uv 10, package 11, Docker 12, Plex removal 13)

**Archives:**

- [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md) — full phase roadmap snapshot
- [v1.2-REQUIREMENTS.md](milestones/v1.2-REQUIREMENTS.md) — UV/DEP/PKG/DOCK/PLEX-REM requirements at close

**Deliverables (high level):** uv-based dependency management with Python 3.13 lockfile; jellyswipe/ package layout with __init__.py, db.py, jellyfin_library.py; multi-stage Docker build using uv; all Plex code, dependencies, and references removed; application verified to work with Jellyfin-only configuration.

**Known gaps at close:** None — all requirements validated

**Deferred items at milestone close:** None reported

---

## v1.1 — Jelly Swipe rename

**Shipped:** 2026-04-24
**Theme:** Product name, Docker image, default SQLite path, Unraid template, and maintainer identity under **AndrewTheTechie**; single fork attribution to upstream in `README.md` / `LICENSE` (and Unraid overview) only.

**Archives:**

- [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md) — milestone snapshot (no numbered phase dirs)
- [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md) — BRAND-01–04 at close

**Deliverables (high level):** Default `jellyswipe.db`, JellySwipe Plex/Jellyfin client strings, UI + PWA manifest titles, `andrewthetechie/jelly-swipe` compose + Docker Hub workflow, GHCR release-on-tag workflow, LICENSE/README/Unraid alignment.

**Tooling note:** `gsd-sdk query milestone.complete` failed (`version required for phases archive`); close completed manually (same pattern as v1.0).

---

## v1.0 — Jellyfin support

**Shipped:** 2026-04-24
**Name:** Jellyfin as alternative media backend (either/or `MEDIA_PROVIDER` per deployment)
**Phases:** 1–9 (implementation 1–5, verification closure 6–7, E2E/validation 8, UI 9)

**Archives:**

- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) — full phase roadmap snapshot
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) — requirement list and traceability at close
- [v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md) — pre-close audit (`ready_for_reaudit`)
- [v1.0-phases/](milestones/v1.0-phases/) — phase execution directories (Phases 1–9) after `/gsd-cleanup`

### What shipped (high level)

1. **Configuration** — Single active provider (`plex` or `jellyfin`), env validation, README / compose notes.
2. **Abstraction** — `LibraryMediaProvider` with Plex and Jellyfin implementations.
3. **Jellyfin core** — Server auth, deck/genres/images, TMDB chain, `/plex/server-info` parity, user-scoped rows and watchlist.
4. **Verification** — Native `*-VERIFICATION.md` / `*-VALIDATION.md` closure for foundation and Jellyfin parity.
5. **Operator narrative** — `08-E2E.md` and validation tables for re-audit.
6. **UI (Phase 9)** — Server-delegated Jellyfin browser session (no env-token JSON leakage) and poster `object-fit: contain` in `templates/index.html` and `data/index.html`.

### Known gaps at close

Documented in the milestone audit; not blocking the **v1.0** tag as shipped product direction.

| ID | Gap | Pointer |
|----|-----|---------|
| ARC-02 | Plex baseline parity checklist remains **partial** | `milestones/v1.0-phases/02-media-provider-abstraction/02-VERIFICATION.md` |
| Traceability | Several J\* rows **Partial** in archived requirements | Native `03-` / `04-` / `05-VERIFICATION.md` under `v1.0-phases/` |
| E2E | `08-E2E.md` operator date tables still **draft** until live runs | `milestones/v1.0-phases/08-e2e-validation-hardening/08-E2E.md` |

### Deferred items at milestone close

`gsd-tools.cjs audit-open` reported **all artifact types clear** (no blocking open debug/UAT items).
