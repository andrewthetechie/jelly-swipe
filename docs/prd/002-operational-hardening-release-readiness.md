# PRD 002 — Operational hardening & release readiness

**Status:** ready for decomposition
**Date:** 2026-05-10
**Driver:** make the container safe to run on shared/Unraid hosts, give operators a real health signal, and replace the ad-hoc `:latest`-tagged release flow with an automated, multi-arch, conventionally-versioned pipeline.

> Decisions in this PRD are recorded in [ADR 0002 — Operational hardening conventions](../adr/0002-operational-hardening-conventions.md).

---

## 1. Why

Three interlocking gaps make the current shape unsuitable for a "give this to a stranger and have them run it on Unraid" baseline:

1. **The container runs as root**, has no `HEALTHCHECK`, and pins `:latest` in `docker-compose.yml`. Operators have no way to distinguish "the app crashed" from "the host took the bind-mount offline," and a `docker pull` at any time can ship them unreleased code.
2. **There is no automated release pipeline.** Tags and GHCR images are produced ad-hoc. There is no `CHANGELOG.md`, no version-bump convention, no automated multi-arch (arm64) build. Unraid users disproportionately run arm hosts; not shipping arm images is an adoption blocker.
3. **The application has no version probe.** `/healthz` does not exist; the only place version lives is `pyproject.toml`. There is no way to confirm-from-outside-the-box which build a running container is.

This PRD defines the cleanup to:

- run the container as a non-root user, with PUID/PGID parameterised so Unraid operators can match it to their host's `nobody:users` (or any other) account;
- expose `/healthz` (liveness) and `/readyz` (dependency probes for Jellyfin + SQLite);
- automate releases with Release Please driven by Conventional Commits, gated by a PR-title check;
- automate multi-arch (amd64 + arm64) Docker image builds on every merge to `main` (rolling `latest`) and on every published release (versioned tags);
- attach OCI labels, SBOM, SLSA provenance, and a Trivy vulnerability report to every published image.

## 2. Scope

### In scope

1. Dockerfile hardening: drop root, parameterise via PUID/PGID entrypoint, add HEALTHCHECK.
2. New entrypoint script handling PUID/PGID, `/app/data` ownership fixup, and privilege drop via `gosu`.
3. New `jellyswipe/routers/health.py` exposing `GET /healthz` (liveness) and `GET /readyz` (dependency probes).
4. `pyproject.toml` is the single source of truth for version; runtime reads via `importlib.metadata`.
5. Release Please workflow (`release-please.yml`) in manifest mode with `release-please-config.json` + `.release-please-manifest.json`.
6. PR title lint workflow (`pr-lint.yml`) enforcing Conventional Commits on PR titles.
7. Replace existing `release-ghcr.yml` with a new tag-triggered multi-arch build/publish workflow.
8. New `docker-main.yml` workflow building/publishing multi-arch images on every push to `main`, tagged `latest` + `main-<sha>`.
9. OCI labels, SBOM, SLSA provenance, and Trivy scan attached to every published image.
10. Docs: README install/upgrade section, `docker-compose.yml`, Unraid template, `ARCHITECTURE.md` "Release & Image Pipeline" section.
11. ADR 0002 capturing the three load-bearing decisions (PUID/PGID, rolling-`latest`, tag-push trigger).
12. Tests for `/healthz` and `/readyz` (success, dependency-failure cases).

### Explicitly out of scope (tracked as follow-ups)

- **Trivy "fail the build on HIGH/CRITICAL CVE"** posture. Initial scan is non-blocking; toggling to blocking is a follow-up once we see the typical churn.
- **Removing `JELLYFIN_USERNAME`/`JELLYFIN_PASSWORD` lines from `docker-compose.yml` and `unraid_template/jelly-swipe.html`** — covered by follow-ups under PRD 001. This PRD updates those files for other reasons; we will *also* drop the deprecated env vars while we are there if PRD 001 has not yet landed, but it is not a primary deliverable.
- **CONTEXT.md update** — this PRD introduces no new domain terms (PUID/PGID/healthz are operational, not domain).
- **Migrating to `release-please`'s `bump-minor-pre-major: true`** behaviour. Default behaviour (every `feat:` → minor bump even pre-1.0) is acceptable.
- **Switching to native ARM runners (`ubuntu-24.04-arm`) for `pr-lint`/`release-please` jobs.** Only the docker build jobs use the arm runner; everything else stays on `ubuntu-latest`.

## 3. Detailed changes

### 3.1 Dockerfile

Apply the following changes to `Dockerfile`. The `USER` directive is **not** added; the entrypoint handles privilege drop. The `gosu` binary is installed from Debian apt.

```dockerfile
# Final stage additions (after existing COPYs)

# Install gosu for privilege drop in entrypoint
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

# Create jellyswipe user/group. Default IDs are Unraid's `nobody:users`
# (PUID=99, PGID=100); the entrypoint can rewrite them at runtime.
RUN groupadd --system --gid 100 jellyswipe \
    && useradd --system --uid 99 --gid 100 \
        --no-create-home --shell /usr/sbin/nologin jellyswipe \
    && mkdir -p /app/data \
    && chown -R jellyswipe:jellyswipe /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5005/healthz', timeout=3).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/app/.venv/bin/python", "-m", "jellyswipe.bootstrap"]
```

Notes:
- `--start-period=60s` is generous for first-boot alembic migrations on slow Unraid hardware. Tune down later if it proves wasteful.
- HEALTHCHECK runs *inside* the container — Docker invokes it as root, regardless of the entrypoint's privilege drop. No PUID/PGID interaction.

### 3.2 `docker-entrypoint.sh` (new file at repo root)

```sh
#!/bin/sh
set -eu

PUID="${PUID:-99}"
PGID="${PGID:-100}"

# If running as root and PUID/PGID don't match the baked-in user, rewrite it.
if [ "$(id -u)" = "0" ]; then
    current_uid="$(id -u jellyswipe)"
    current_gid="$(id -g jellyswipe)"
    if [ "$current_uid" != "$PUID" ] || [ "$current_gid" != "$PGID" ]; then
        groupmod -o -g "$PGID" jellyswipe
        usermod  -o -u "$PUID" -g "$PGID" jellyswipe
    fi
    # Ensure /app/data is writable by the runtime user. Fast no-op when correct.
    chown -R jellyswipe:jellyswipe /app/data
    exec gosu jellyswipe "$@"
fi

# Already non-root (e.g. user passed `--user` on `docker run`). Exec directly;
# operator is responsible for ensuring /app/data is writable.
exec "$@"
```

### 3.3 `jellyswipe/routers/health.py` (new)

Mounts two endpoints at root (no prefix, per the project's `D-14` router convention):

- `GET /healthz` — liveness. Returns `200 {"status": "ok", "version": <version>}`. Never touches Jellyfin or SQLite. Version lookup wrapped in try/except; on failure returns `"version": "unknown"` but still 200 — liveness is independent of metadata.
- `GET /readyz` — readiness. Runs the SQLite and Jellyfin probes in parallel (`asyncio.gather`). Returns:
  - `200 {"status": "ok", "checks": {"sqlite": "ok", "jellyfin": "ok"}}` when both succeed;
  - `503 {"status": "degraded", "checks": {"sqlite": "ok", "jellyfin": "fail: <reason>"}}` if any fail.

Probe details:

| Check | Mechanism | Timeout |
| --- | --- | --- |
| `sqlite` | `SELECT 1` via existing engine connection | 1s |
| `jellyfin` | `GET {JELLYFIN_URL}/System/Info/Public` (unauthenticated) | 2s |

Both endpoints are unauthenticated (no session cookie required). The Jellyfin probe deliberately uses `/System/Info/Public` and not an authenticated endpoint — boot-time validation already exercises the API key, and `/readyz` only needs to confirm network reachability.

Module shape:

```python
from importlib.metadata import version as _pkg_version, PackageNotFoundError

try:
    __version__ = _pkg_version("jellyswipe")
except PackageNotFoundError:
    __version__ = "unknown"

health_router = APIRouter()

@health_router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}

@health_router.get("/readyz")
async def readyz(response: Response) -> dict:
    sqlite_status, jellyfin_status = await asyncio.gather(
        _check_sqlite(),
        _check_jellyfin(),
    )
    ok = sqlite_status == "ok" and jellyfin_status == "ok"
    response.status_code = 200 if ok else 503
    return {
        "status": "ok" if ok else "degraded",
        "checks": {"sqlite": sqlite_status, "jellyfin": jellyfin_status},
    }
```

Register the router in the bootstrap alongside the others.

### 3.4 `.github/workflows/release-please.yml` (new)

```yaml
name: release-please

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    steps:
      - uses: googleapis/release-please-action@v4
        with:
          # Default GITHUB_TOKEN. Downstream docker workflow is triggered via
          # push: tags: ['v*'] (which fires under GITHUB_TOKEN), not via
          # release: events (which do not fire under GITHUB_TOKEN).
          token: ${{ secrets.GITHUB_TOKEN }}
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json
```

### 3.5 `release-please-config.json` (new, repo root)

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "include-v-in-tag": true,
  "include-component-in-tag": false,
  "bootstrap-sha": "<sha of merge commit; fill in at PR time>",
  "packages": {
    ".": {
      "package-name": "jellyswipe",
      "release-type": "python",
      "changelog-path": "CHANGELOG.md"
    }
  }
}
```

### 3.6 `.release-please-manifest.json` (new, repo root)

```json
{
  ".": "0.1.0"
}
```

### 3.7 `.github/workflows/pr-lint.yml` (new)

```yaml
name: PR Title Lint

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

permissions:
  pull-requests: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: amannn/action-semantic-pull-request@v5
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          types: |
            feat
            fix
            docs
            chore
            refactor
            test
            ci
            build
            perf
            revert
          requireScope: false
```

### 3.8 `.github/workflows/release-ghcr.yml` — REPLACE

Replace the existing file (currently `release: types: [created]`, amd64-only) with the tag-push-triggered, multi-arch workflow described below.

```yaml
name: Publish release image

on:
  push:
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

permissions:
  contents: read
  packages: write
  id-token: write          # provenance signing
  attestations: write      # SBOM/provenance attestations

jobs:
  build:
    strategy:
      matrix:
        include:
          - runner: ubuntu-latest
            platform: linux/amd64
            arch: amd64
          - runner: ubuntu-24.04-arm
            platform: linux/arm64
            arch: arm64
    runs-on: ${{ matrix.runner }}
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push by digest
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: ${{ matrix.platform }}
          outputs: type=image,name=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }},push-by-digest=true,name-canonical=true,push=true
          provenance: mode=max
          sbom: true
          cache-from: type=gha,scope=release-${{ matrix.arch }}
          cache-to:   type=gha,scope=release-${{ matrix.arch }},mode=max
          labels: |
            org.opencontainers.image.source=https://github.com/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}
            org.opencontainers.image.version=${{ github.ref_name }}
            org.opencontainers.image.created=${{ github.event.repository.updated_at }}

      - name: Export digest
        run: |
          mkdir -p /tmp/digests
          echo "${{ steps.build.outputs.digest }}" > /tmp/digests/${{ matrix.arch }}

      - uses: actions/upload-artifact@v4
        with:
          name: digest-${{ matrix.arch }}
          path: /tmp/digests/${{ matrix.arch }}

  merge:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: /tmp/digests
          pattern: digest-*
          merge-multiple: true

      - uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Compute tags
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=semver,pattern=v{{version}}
            type=semver,pattern=v{{major}}.{{minor}}
            type=semver,pattern=v{{major}}
            type=sha,format=long,prefix=

      - name: Create manifest list
        run: |
          DIGESTS=""
          for f in /tmp/digests/*; do
            DIGESTS="$DIGESTS ${REGISTRY}/${IMAGE_NAME}@$(cat $f)"
          done
          for tag in $(jq -r '.[]' <<< '${{ steps.meta.outputs.json }}' | jq -r '.tags[]?'); do
            docker buildx imagetools create -t $tag $DIGESTS
          done

      - name: Trivy scan (non-blocking)
        uses: aquasecurity/trivy-action@master
        continue-on-error: true
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.ref_name }}
          format: sarif
          output: trivy-results.sarif
          severity: HIGH,CRITICAL

      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: trivy-results.sarif
```

Notes:
- The release workflow **does not** push `latest`. `latest` is owned by the main-branch workflow.
- Tags on a release `v0.2.0`: `v0.2.0`, `v0.2`, `v0`, and the long SHA.
- Trivy uploads to GitHub's security tab (Code scanning alerts) and never fails the build.

### 3.9 `.github/workflows/docker-main.yml` (new)

```yaml
name: Publish main image

on:
  push:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

permissions:
  contents: read
  packages: write
  id-token: write
  attestations: write

jobs:
  build:
    strategy:
      matrix:
        include:
          - runner: ubuntu-latest
            platform: linux/amd64
            arch: amd64
          - runner: ubuntu-24.04-arm
            platform: linux/arm64
            arch: arm64
    runs-on: ${{ matrix.runner }}
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: ${{ matrix.platform }}
          outputs: type=image,name=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }},push-by-digest=true,name-canonical=true,push=true
          provenance: mode=max
          sbom: true
          cache-from: type=gha,scope=main-${{ matrix.arch }}
          cache-to:   type=gha,scope=main-${{ matrix.arch }},mode=max
          labels: |
            org.opencontainers.image.source=https://github.com/${{ github.repository }}
            org.opencontainers.image.revision=${{ github.sha }}
            org.opencontainers.image.version=main-${{ github.sha }}
            org.opencontainers.image.created=${{ github.event.repository.updated_at }}
      - run: |
          mkdir -p /tmp/digests
          echo "${{ steps.build.outputs.digest }}" > /tmp/digests/${{ matrix.arch }}
      - uses: actions/upload-artifact@v4
        with:
          name: digest-${{ matrix.arch }}
          path: /tmp/digests/${{ matrix.arch }}

  merge:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/download-artifact@v4
        with: { path: /tmp/digests, pattern: digest-*, merge-multiple: true }
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Create manifest list (latest + main-<sha>)
        run: |
          DIGESTS=""
          for f in /tmp/digests/*; do
            DIGESTS="$DIGESTS ${REGISTRY}/${IMAGE_NAME}@$(cat $f)"
          done
          docker buildx imagetools create \
            -t ${REGISTRY}/${IMAGE_NAME}:latest \
            -t ${REGISTRY}/${IMAGE_NAME}:main-${{ github.sha }} \
            $DIGESTS
```

### 3.10 Doc updates

#### `README.md`
- Add a **PUID/PGID** row to the env-var table; default `99`/`100`; describe as "the uid/gid the app process runs as inside the container — set to match the owner of your bind-mounted `./data` directory."
- Add an **Installation** subsection recommending users pin to a versioned tag: `image: ghcr.io/andrewthetechie/jelly-swipe:v0.2.0` (substituting the latest release).
- Add an **Upgrading** subsection:
  - Note that `:latest` is the rolling tip of `main`, not the newest release.
  - For pre-PUID/PGID upgraders: either set `PUID`/`PGID` to match your existing `./data` owner (`stat -c '%u %g' ./data`), or `chown -R 99:100 ./data` once.
- Add a **Health probes** subsection documenting `/healthz` and `/readyz`, their semantics, and the expected response shapes.

#### `docker-compose.yml`
- Change `image: andrewthetechie/jelly-swipe:latest` → `image: ghcr.io/andrewthetechie/jelly-swipe:v0.2.0` with a comment `# Pin to a release. :latest tracks main and may include unreleased changes.`
- Add `environment:` entries `PUID=99` and `PGID=100` with comments referencing the README.
- Remove the commented-out `JELLYFIN_USERNAME` / `JELLYFIN_PASSWORD` lines (PRD 001 follow-up; aligned with current state).

#### `unraid_template/jelly-swipe.html`
- Pin the `<Repository>` to `ghcr.io/andrewthetechie/jelly-swipe:v0.2.0` (or the current released version at template-update time).
- Add `<Config>` rows for `PUID` (default `99`) and `PGID` (default `100`), labelled "User ID" and "Group ID" with the standard Unraid description ("Sets the user/group ID inside the container.").
- Verify the data-dir mapping is `/app/data`. (No change expected.)
- If the lint script `scripts/lint-unraid-template.py` enforces an env-var allowlist, add `PUID` and `PGID` to it.

#### `ARCHITECTURE.md`
- Add a new section: **Release & Image Pipeline** describing:
  - Conventional Commits → Release Please → versioned tags.
  - `push: tags: ['v*']` triggers the release docker build (multi-arch, SBOM, provenance, Trivy).
  - `push: branches: [main]` triggers the rolling-`latest` docker build.
  - Tag set: `vX.Y.Z`, `vX.Y`, `vX`, long SHA on releases; `latest` and `main-<sha>` on main.
  - Why the `GITHUB_TOKEN` constraint forces tag-push rather than `release:` trigger (link the ADR).
- Add a paragraph under the deployment section describing `/healthz` and `/readyz`.

### 3.11 Tests (new)

In `tests/test_routes_health.py`:

1. `GET /healthz` returns 200, body has `status == "ok"` and a string `version`.
2. `GET /healthz` does **not** touch the Jellyfin client (fake provider's call counter remains 0).
3. `GET /healthz` does **not** issue a `SELECT` (assert via SQLAlchemy event listener or by injecting a sentinel engine).
4. `GET /readyz` when both probes succeed returns 200, `status == "ok"`, both checks `"ok"`.
5. `GET /readyz` when the Jellyfin probe times out returns 503, `status == "degraded"`, `checks.jellyfin` starts with `"fail:"`.
6. `GET /readyz` when SQLite probe raises returns 503 with `checks.sqlite` starting with `"fail:"`.
7. Both endpoints are reachable without a session cookie (regression fence).

In `tests/test_route_authorization.py` (existing): add `/healthz` and `/readyz` to the unauthenticated-route allowlist.

In `tests/test_routes_xss.py` (existing): no entry needed — these endpoints take no input.

### 3.12 ADR 0002

Create `docs/adr/0002-operational-hardening-conventions.md`. Covers:

1. PUID/PGID entrypoint pattern (over static UID).
2. Rolling-`latest` from `main` (over release-`latest`).
3. Tag-push docker-build trigger (over `release:` trigger), with the `GITHUB_TOKEN` rationale.

## 4. Boot-time behaviour after this PRD lands

| Scenario | Outcome |
| --- | --- |
| Fresh install, no PUID/PGID set, no existing `./data` | Container starts as uid 99/gid 100. Creates `./data` owned by 99:100 on the host. |
| Upgrader, existing `./data` owned by root | Operator either (a) sets PUID/PGID to 0 (not recommended), (b) `chown -R 99:100 ./data` once, or (c) sets PUID/PGID to match existing owner. Without one of these, the container crashes during the entrypoint's `chown -R` step — but with a clear log message because `chown` errors are not silent. |
| Upgrader, existing `./data` owned by some unraid user (e.g. `1000:1000`) | Operator sets `PUID=1000 PGID=1000`. Entrypoint rewrites uid/gid, chown is a no-op, container runs as that user. |
| `docker run --user 1234:5678` | Entrypoint detects non-root, skips PUID/PGID rewrite and chown, execs the CMD directly. Operator takes responsibility for `./data` permissions. |
| Cold boot on slow Unraid hardware (alembic migration ~30s) | Docker HEALTHCHECK gives 60s of grace before counting failures; container shows `health: starting` during migrations, then `health: healthy` once `/healthz` responds. |
| Jellyfin unreachable | `/readyz` returns 503; `/healthz` still 200; Docker HEALTHCHECK stays healthy (does not flap on dependency outages). |

## 5. Acceptance criteria

1. `Dockerfile` contains no `USER` directive; entrypoint installs and `exec`s via `gosu`.
2. `docker run -e PUID=1234 -e PGID=5678 <image> id` prints `uid=1234 gid=5678`.
3. `docker inspect <container> | jq '.[0].State.Health'` reports `healthy` within 90s of boot on a typical dev machine.
4. `curl http://localhost:5005/healthz` returns `200 {"status":"ok","version":"<semver>"}` with no Jellyfin or DB access (verified via mock-call counters in tests).
5. `curl http://localhost:5005/readyz` returns `200` with both checks `"ok"` when Jellyfin and SQLite are reachable.
6. `curl http://localhost:5005/readyz` returns `503` when `JELLYFIN_URL` points at a black hole.
7. Merging a `feat:` commit to `main` opens a release PR titled `chore(main): release X.Y.Z`.
8. Merging that release PR creates a `vX.Y.Z` tag and a matching GitHub Release.
9. Within 10 minutes of the tag push, the GHCR image manifest for `vX.Y.Z` contains both `linux/amd64` and `linux/arm64` entries.
10. The same manifest also exists at `vX.Y`, `vX`, and the long SHA.
11. A merge to `main` (non-release) updates `:latest` and creates a `:main-<sha>` tag — both multi-arch.
12. Every published image has `org.opencontainers.image.source`, `version`, `revision`, `created` labels and an SBOM/provenance attestation visible in `docker buildx imagetools inspect`.
13. Opening a PR titled `update stuff` fails the PR-title-lint check.
14. The Trivy SARIF upload appears in the Security → Code scanning tab in GitHub.
15. `README.md`, `docker-compose.yml`, and the Unraid template pin to a versioned tag and document PUID/PGID.
16. `ARCHITECTURE.md` has a "Release & Image Pipeline" section.
17. `docs/adr/0002-operational-hardening-conventions.md` exists and is referenced from this PRD.

## 6. Risks

- **Bind-mount permission breakage for upgraders.** If an existing user doesn't read the upgrade notes, the container will fail on first boot of the new image. The entrypoint logs a clear `chown` error, but operators have to be looking. Mitigated by README + GitHub Release notes; not mitigated by a deprecation period.
- **arm64 emulation-free build via `ubuntu-24.04-arm` depends on GitHub's hosted runner availability.** If the arm runner pool is exhausted or removed, the build will queue or fail. Mitigation: switch back to QEMU emulation by replacing the matrix's arm runner with `ubuntu-latest` and adding `docker/setup-qemu-action`.
- **Multi-arch manifest creation via `docker buildx imagetools create`** is a single non-atomic operation. A failed `merge` job after a successful per-arch build leaves orphan digests in GHCR (no tags pointing at them). They age out via untagged-image retention; document the cleanup if it becomes noisy.
- **Trivy "non-blocking" posture means a new CVE in `python:3.13-slim` will not fail releases.** This is deliberate — we want zero-friction release cadence — but it means operators must read the Security tab to learn about CVEs. Surfaced in ADR 0002.
- **Rolling-`latest` will surprise anyone who treats `:latest` as a stable tag.** Mitigated by README, compose, and Unraid template all pinning a `vX.Y.Z` and explicitly documenting the meaning. Not mitigated by any in-image signal.
- **First Release Please run requires a `bootstrap-sha` pinned at the merge SHA of the release-please workflow's own introduction.** Forgetting to set it means the release-please walks the full repo history and may build an absurd first changelog or stall. The author of the PR that introduces this PRD's workflow files is responsible for filling in the SHA at PR time.
- **`importlib.metadata.version("jellyswipe")` returns the version baked into the installed package at image build time.** A bind-mounted source-code overlay (developer workflow) that points at uninstalled source will report `version: "unknown"`. This is acceptable — `/healthz` is meant for the deployed image, not the dev loop.

## 7. Follow-ups (not part of this PRD)

- Toggle Trivy from non-blocking to blocking on HIGH/CRITICAL once we see the first month of CVE noise.
- Switch the docker build jobs to QEMU on `ubuntu-latest` if GitHub's hosted arm runner stops being available, or keep both as an environment-variable-switchable matrix.
- Add a `/version` endpoint distinct from `/healthz` if any tooling ends up wanting the version without the liveness contract.
- Tag major and minor floating tags (`vX`, `vX.Y`) for the **main-rolling** workflow too, if anyone asks for a "stay on 0.2.x main" channel.
- Consider attaching cosign signatures to the manifest list (provenance/SBOM are already attached, but signing the manifest itself is a separate step).
- Reconcile `unraid_template/jelly-swipe.html` and `docker-compose.yml` with PRD 001's USERNAME/PASSWORD cleanup if those files still carry residual lines after PRD 001 lands.

## 8. References

- [ADR 0002 — Operational hardening conventions](../adr/0002-operational-hardening-conventions.md)
- [PRD 001 — Remove residual username/password auth code paths](./001-remove-username-password-auth.md)
- [Release Please documentation](https://github.com/googleapis/release-please-action)
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
