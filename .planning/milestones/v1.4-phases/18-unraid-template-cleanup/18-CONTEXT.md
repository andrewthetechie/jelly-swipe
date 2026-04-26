# Phase 18: Unraid Template Cleanup - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Update the Unraid template (`unraid_template/jelly-swipe.html`) to use Jellyfin environment variables instead of removed Plex variables, ensuring users can successfully deploy the application. Remove fake placeholder values and add CI validation to prevent future template drift.

</domain>

<decisions>
## Implementation Decisions

### Template Variables
- **D-01:** Template will use Jellyfin authentication method: API key only
  - Include `JELLYFIN_URL` and `JELLYFIN_API_KEY` in both `<Variable>` and `<Config>` sections
  - Do NOT include `JELLYFIN_USERNAME` or `JELLYFIN_PASSWORD` (app supports them but template won't expose them)
  - Remove all references to `PLEX_URL` and `PLEX_TOKEN`
  - Include `TMDB_API_KEY` and `FLASK_SECRET` (already present, just clean up placeholders)

### Template UX
- **D-02:** All fields will be blank by default
  - Masked fields (`JELLYFIN_API_KEY`, `TMDB_API_KEY`, `FLASK_SECRET`): empty `<Value>` and `Default=""`
  - Non-masked field (`JELLYFIN_URL`): empty `<Value>` and `Default=""`
  - Remove all fake placeholder values: "YOUR_PLEX_URL", "YOUR_PLEX_TOKEN", "YOUR_TMDB_API_KEY", "Enter_random_string"

### CI Validation
- **D-03:** Create separate GitHub Actions workflow: `.github/workflows/unraid-template-lint.yml`
  - Workflow name: "Unraid Template Lint"
  - Trigger: push and pull_request on `unraid_template/jelly-swipe.html`
  - Lint implementation: Python script that:
    - Parses the Unraid template XML
    - Extracts all variable names from `<Variable>` and `<Config>` sections
    - Compares against recognized app env vars: `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `TMDB_API_KEY`, `FLASK_SECRET`, `DB_PATH`, `JELLYFIN_DEVICE_ID`
    - Fails if template contains any variable not in the recognized set (strict subset)
  - Failure behavior: Block PR — workflow exits with error code to prevent merge
  - Success behavior: Pass silently, allows merge to proceed

### the agent's Discretion
- Exact Python script structure for lint implementation
- Specific GitHub Actions syntax and versioning
- Error message formatting for lint failures
- Whether to add a README section documenting the lint step

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Issue and Requirements
- `.planning/REQUIREMENTS.md` — v1.4 requirements (TEMP-01 through CI-01)
- `.planning/ROADMAP.md` — Phase 18 goals and success criteria

### Application Code
- `jellyswipe/__init__.py` — Flask app initialization, env var validation (lines with `os.getenv`)
- `jellyswipe/jellyfin_library.py` — Jellyfin provider, authentication logic (lines with `os.getenv`)

### Unraid Template
- `unraid_template/jelly-swipe.html` — Current template with Plex variables (lines 39-73 for Environment and Config sections)

### CI Workflows
- `.github/workflows/test.yml` — Existing test workflow (reference for Python environment setup)
- `.github/workflows/docker-image.yml` — Existing Docker workflow (reference for Unraid template usage context)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- GitHub Actions workflows: Existing Python 3.13 environment in test.yml can be referenced for lint workflow
- Unraid template structure: Current template has `<Variable>` (legacy format) and `<Config>` (modern format) sections

### Established Patterns
- Python 3.13 with uv for CI dependencies (from test.yml)
- GitHub Actions workflow structure: name, on/trigger, jobs, steps with checkout, setup, run
- Unraid template XML format: `<Container>` → `<Environment>` → `<Variable>` entries and `<Config>` entries at container level

### Integration Points
- New lint workflow: Independent job, runs in parallel with test.yml and docker-image.yml
- Template variables: Must match exactly what `jellyswipe/__init__.py` and `jellyswipe/jellyfin_library.py` expect

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for CI linting and Unraid template maintenance.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 18-unraid-template-cleanup*
*Context gathered: 2026-04-25*
