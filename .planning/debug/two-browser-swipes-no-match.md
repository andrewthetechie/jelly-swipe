---
status: resolved
trigger: "when running this branch, in solo mode swipes work and matches are shown but in two separate browser windows, one in private mode and one not, both sessions join the room but swipes never match up. No match popups are triggered and the Matches page shows no Matches, even when both windows have swiped right. There are no errors in the webdev network or console tab."
created: 2026-05-05
updated: 2026-05-05
---

# Debug Session: Two Browser Swipes No Match

## Symptoms

- expected_behavior: Two separate browser sessions in the same room should create a match when both users swipe right on the same movie, trigger match popups, and show the match on the Matches page.
- actual_behavior: Both sessions can join the room and swipe, but reciprocal right swipes never match. No match popup appears and the Matches page shows no matches.
- error_messages: No browser network errors or console errors reported.
- timeline: Observed on the current PR branch.
- reproduction: Open one normal browser window and one private browser window, join both sessions to the same room, swipe right on the same movie in both sessions.

## Current Focus

- hypothesis: multi-user matching incorrectly treats Jellyfin user_id as the room participant identity
- test: reproduce via route/database-level two-session swipe flow
- expecting: reciprocal right swipes should create a row visible to the room match listing
- next_action: run full suite and commit fix
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-05-05
  observation: Existing multi-user match query required `user_id != current_user_id`, so two browser sessions authenticated as the same Jellyfin user could not match.
- timestamp: 2026-05-05
  observation: New regression `test_same_jellyfin_user_separate_sessions_can_match` failed before the fix with zero match rows.
- timestamp: 2026-05-05
  observation: After switching participant separation to `session_id` when available, same-user separate-session match regression and existing different-user match tests passed.

## Eliminated

- hypothesis: SSE delivery failure only
  reason: The database never created a match row before the fix, so the popup and Matches page had no match to display.

## Resolution

- root_cause: Multi-user match detection used Jellyfin `user_id` as the participant boundary. Two browser windows using the same Jellyfin identity had distinct session IDs but identical user IDs, so reciprocal right swipes were filtered out.
- fix: Use browser `session_id` to distinguish room participants when present, keep `user_id` as a fallback for sessionless legacy/test requests, and update `last_match_data` even when both sessions share the same user ID.
- verification: Targeted same-user and different-user match tests passed.
- files_changed: jellyswipe/routers/rooms.py, tests/test_route_authorization.py
