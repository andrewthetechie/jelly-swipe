# ADR 0002 — Operational hardening conventions

**Status:** Accepted
**Date:** 2026-05-10
**Deciders:** project owner
**Related:** [PRD 002 — Operational hardening & release readiness](../prd/002-operational-hardening-release-readiness.md)

---

## Context

The work to ship Jelly-Swipe as a first-class self-hosted application (Unraid template, GHCR images, automated releases) surfaced three load-bearing decisions that are individually small but jointly shape the operational contract with operators:

1. **How the container runs as a non-root user** — what UID it uses, who chooses it, and how upgraders who already have a `./data` directory owned by root survive the transition.
2. **What `latest` means** — does it track the newest release, or the tip of `main`? This determines what a `docker pull` does for someone who pinned to `:latest`.
3. **What triggers the multi-arch docker build** — `release: published` events or `push: tags: ['v*']`? The choice is constrained by the `GITHUB_TOKEN`-cannot-trigger-downstream-workflows rule.

These three decisions interact: the PUID/PGID pattern determines the entrypoint shape, the `latest`-semantics decision determines which workflow owns which tag, and the trigger choice determines whether the docker workflow runs at all on releases. Capturing them together preserves the cross-references.

## Decision

### 1. PUID/PGID entrypoint pattern (over static UID)

The container ships with `jellyswipe:jellyswipe` defaulting to `uid=99, gid=100` (Unraid's `nobody:users`). On every boot, an entrypoint script reads `PUID` and `PGID` env vars (defaulting to 99/100), rewrites the `jellyswipe` user's IDs to match, `chown -R`s `/app/data`, and `exec`s the application via `gosu jellyswipe`. If the container is already running as a non-root user (operator passed `--user`), the entrypoint skips the rewrite and execs directly.

### 2. Rolling-`latest` from `main`

`ghcr.io/<owner>/jelly-swipe:latest` is published by the **main-branch** docker build workflow on every merge to `main`. The **release** docker build workflow publishes versioned tags (`vX.Y.Z`, `vX.Y`, `vX`, long SHA) but **does not** touch `latest`. Operators who want stability pin to a versioned tag; `:latest` is documented as "the rolling tip of `main`."

### 3. Tag-push docker-build trigger (over `release:` trigger)

The release docker workflow triggers on `push: tags: ['v*']`, not on `release: types: [published]`. Release Please uses the default `GITHUB_TOKEN`, and per GitHub's documented behaviour, events created by the `GITHUB_TOKEN` (including `release`) do not trigger downstream workflow runs. Tag push *does* fire under the `GITHUB_TOKEN`, so the docker build runs reliably without requiring a PAT.

## Alternatives considered

### Alt 1a. Static UID 10001 + readme migration step
Hardcode `useradd --uid 10001`. Document `chown -R 10001:10001 ./data` as a one-time upgrade step.

**Rejected because:** Unraid is a first-class deployment target (we ship an Unraid template), and Unraid operators expect PUID/PGID — every linuxserver.io image they have ever pulled exposes those variables, and they map them to Unraid's user model. Shipping a static UID would make us an outlier on a platform where the convention is established.

### Alt 1b. Static UID 10001 + entrypoint chown-then-drop
Hardcode `--uid 10001` but ship an entrypoint that always `chown`s `/app/data` and drops privileges. Solves the upgrade-permission problem without requiring operator action.

**Rejected because:** it solves only half of the Unraid UX problem. Unraid operators still cannot align the container's runtime user with their host's filesystem ownership without forking the image. PUID/PGID solves both problems with one mechanism for marginal additional entrypoint complexity.

### Alt 2a. Release-`latest`, `edge` from main
`:latest` only moves on releases; main builds tag `:edge`. Standard convention in many projects.

**Rejected because:** the operator brief that drove this work explicitly asked for "build and push the arm and x86 docker images from Dockerfile and tag it with the hash and latest" on every merge to main. Release-`latest` would contradict that brief, and the cost is purely a documentation discipline question — pin `vX.Y.Z` and the meaning of `:latest` doesn't matter. We chose to honour the brief and pay the documentation cost.

### Alt 2b. Three channels: `edge`, `main-<sha>`, and `latest` (= newest release)
Most expressive: operators can pin to any of three semantic channels.

**Rejected because:** three named channels is one more concept than the project needs at its current size, and `:latest` = main meets every consumer scenario we have. Revisit if a stable-floating channel becomes a real request.

### Alt 3a. Use a PAT (`RELEASE_PLEASE_TOKEN`)
Configure Release Please with a Personal Access Token. PAT-created release events *do* fire downstream workflows, so the docker workflow can keep its `release: published` trigger.

**Rejected because:** PATs require human ownership (they're tied to a user account), have implicit broad scopes unless meticulously trimmed via fine-grained PATs, and expire. The constraint "no PAT" was explicit in the operator brief, and the tag-push alternative achieves the same outcome without any of those operational costs.

### Alt 3b. Inline the docker build into the release-please workflow
Keep the default `GITHUB_TOKEN`, but make the docker build a follow-on step inside the release-please workflow, gated on the `release_created` output.

**Rejected because:** it couples two concerns (release tagging and image publishing) into one workflow whose execution time becomes "release-please latency + multi-arch build latency." A failure in the docker step leaves a published release with no image attached and a confusing workflow status. Tag-push keeps the two workflows independently observable, independently retry-able, and independently revertable.

## Consequences

### Positive
- **Aligned with Unraid conventions.** PUID/PGID is what Unraid operators expect; the template can expose them as standard Config rows.
- **Operator-honest `latest`.** `:latest` accurately describes what it is (rolling main); anyone wanting stability pins. No silent surprise upgrades on `:latest`.
- **No PAT operational burden.** All workflows run on the built-in `GITHUB_TOKEN`. No expiring credentials, no per-user account coupling.
- **Independently observable release pipelines.** The release-PR-merge → tag → image-build chain is three independently retry-able steps, each visible in the Actions tab.

### Negative
- **PUID/PGID adds entrypoint complexity** (~25 lines of shell, a `gosu` dependency). A static UID would have been a 3-line Dockerfile change.
- **Rolling-`latest` is a foot-gun** for anyone treating `:latest` as a stable tag — but only if they ignore the README, the compose comment, and the Unraid template's pinned tag, all of which point them at `vX.Y.Z`. Mitigated through documentation, not through technical means.
- **Tag-push trigger loses access to `release.html_url` and other release-event payload fields** that the `release:` trigger would have given for free. Worked around by reading `github.ref_name` (the tag) and reconstructing release URLs from `github.repository`.
- **Orphan digests** when the manifest-merge job fails after a successful per-arch build. They age out via GHCR's untagged retention, but the failure mode is silent in the registry UI.
- **No `release.published` signal means downstream automation (e.g. a homelab "notify me on new release" workflow) must listen on tag push or releases-RSS instead.**

## Implementation reference

See [PRD 002](../prd/002-operational-hardening-release-readiness.md) §3 for the file-by-file plan, §5 for acceptance criteria, and §6 for the full risk register.
