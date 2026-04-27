# Phase 25: Config & Deploy Cleanup - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove all Plex references from deployment and configuration artifacts (manifests, templates, requirements) and delete the dead `data/index.html` PWA shell. Purely deletion and text updates — no new features.

</domain>

<decisions>
## Implementation Decisions

### Manifest descriptions (CFG-01)
- **D-01:** Update both `jellyswipe/static/manifest.json` and `data/manifest.json` `description` field from `"Tinder-style movie matching for your Plex or Jellyfin library."` to `"Tinder-style movie matching for your Jellyfin library."`. Simple find-and-replace — drop "Plex or " from the sentence.

### Dead PWA shell (CFG-02)
- **D-02:** Delete `data/index.html` entirely. It is a never-fetched PWA shell (1032 lines) containing all the stale Plex references that Phase 24 cleaned from the live template. Nothing references or serves this file — safe to remove.

### Unraid template (CFG-03)
- **D-03:** CFG-03 is pre-completed. The Unraid template (`unraid_template/jelly-swipe.html`) contains zero Plex references — only Jellyfin environment variables. This was cleaned in a prior milestone. No changes needed.

### requirements.txt (CFG-04)
- **D-04:** Delete `requirements.txt` entirely. The file is deprecated (header says "use uv"), Docker uses `pyproject.toml` + `uv.lock`, and it contains the `plexapi` dependency. `pyproject.toml` is the canonical dependency source.

### Agent's Discretion
- Whether to also remove any references to `requirements.txt` from documentation (README, comments) if found during the sweep
- Exact git commit structure for the deletions

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements
- `.planning/REQUIREMENTS.md` — CFG-01, CFG-02, CFG-03, CFG-04 requirements and acceptance criteria
- `.planning/ROADMAP.md` § Phase 25 — success criteria (4 items)

### Target files
- `jellyswipe/static/manifest.json` — PWA manifest (description update)
- `data/manifest.json` — duplicate PWA manifest (description update)
- `data/index.html` — dead PWA shell (delete)
- `requirements.txt` — deprecated dependency file (delete)
- `unraid_template/jelly-swipe.html` — already clean (verify, no changes needed)

### Prior phase context
- `.planning/phases/23-backend-source-cleanup/23-CONTEXT.md` — Phase 23 deleted `/plex/server-info` route
- `.planning/phases/24-frontend-plex-cleanup/24-CONTEXT.md` — Phase 24 cleaned all Plex refs from live template

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Both `manifest.json` files are identical — simple text replacement in both
- `data/index.html` is a standalone file with no imports or dependents

### Established Patterns
- Configuration files are standalone JSON/XML — edits are self-contained
- Deletion leaves no orphaned references (verified: no route serves `data/index.html`, no template includes it)

### Integration Points
- `sw.js` or other PWA files — verify `data/index.html` deletion doesn't break scope (per STATE.md concern, file was never fetched)
- README may reference `requirements.txt` — check and update if found during sweep

</code_context>

<specifics>
## Specific Ideas

- Manifest description: "Tinder-style movie matching for your Jellyfin library." — user chose the simplest option (just drop "Plex or")
- CFG-03 pre-completion should be noted in any verification report so Phase 26 acceptance sweep doesn't flag it as "missed"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-config-deploy-cleanup*
*Context gathered: 2026-04-26*
