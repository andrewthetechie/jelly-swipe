# Phase 27: SSRF Protection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in 27-CONTEXT.md — this log preserves the Q&A.

**Date:** 2026-04-27
**Phase:** 27-ssrf-protection
**Mode:** discuss (--all --batch)
**Areas discussed:** 2 batches, 6 questions

## Questions and Answers

### Batch 1: Core Validation Design

| Q# | Area | Options Presented | User Selection |
|----|------|-------------------|----------------|
| Q1 | IPv6 scope | (1) IPv6 too / (2) IPv4 only / (3) You decide | **(1) IPv6 too** — Block `::1`, `fc00::/7`, `fe80::/10` |
| Q2 | DNS resolution failure | (1) Hard fail at boot / (2) Warn but allow / (3) You decide | **(1) Hard fail at boot** — RuntimeError, no startup |
| Q3 | Module placement | (1) ssrf_validator.py / (2) Inline in __init__.py / (3) You decide | **(1) ssrf_validator.py** — Separate module |

### Batch 2: Security Behavior

| Q# | Area | Options Presented | User Selection |
|----|------|-------------------|----------------|
| Q4 | DNS rebinding strategy | (1) Cache resolved IP / (2) Boot-only, accept risk / (3) Periodic re-validation | **(2) Boot-only, accept risk** — Self-hosted app, operator controls DNS |
| Q5 | Validation timing | (1) Boot only, single point / (2) Boot + lazy re-check / (3) You decide | **(1) Boot only, single point** — Lines 27-45, after presence check |
| Q6 | Override semantics | (1) Exact "1" match / (2) Truthy check / (3) You decide | **(1) Exact "1" match** — `os.getenv("ALLOW_PRIVATE_JELLYFIN") == "1"` |

## Summary

All 6 questions resolved in 2 batches. No corrections needed. No deferred ideas.
