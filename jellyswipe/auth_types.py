"""Shared auth session service and repository types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AuthRecord:
    session_id: str
    jf_token: str
    user_id: str
    created_at: str
