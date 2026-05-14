"""Pydantic v2 models for authentication API responses."""

from typing import Optional

from pydantic import BaseModel, Field


class LoginResponse(BaseModel):
    """Response from /auth/jellyfin-use-server-identity endpoint."""

    userId: str = Field(..., description="The authenticated user's ID from Jellyfin")


class LogoutResponse(BaseModel):
    """Response from /auth/logout endpoint."""

    status: str = Field(..., description="Logout status, typically 'logged_out'")


class MeResponse(BaseModel):
    """Response from /me endpoint with current user and server info."""

    userId: str = Field(..., description="The authenticated user's ID from Jellyfin")
    displayName: str = Field(..., description="User's display name")
    serverName: str = Field(..., description="Jellyfin server name")
    serverId: str = Field(..., description="Jellyfin server machine identifier")
    activeRoom: Optional[str] = Field(
        default=None, description="ID of the currently active swipe room, if any"
    )


class ServerInfoResponse(BaseModel):
    """Response from /jellyfin/server-info endpoint with server identifiers."""

    baseUrl: str = Field(..., description="Jellyfin server machine identifier")
    webUrl: str = Field(..., description="Jellyfin server web URL")
