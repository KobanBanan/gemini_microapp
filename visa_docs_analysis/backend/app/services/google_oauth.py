from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from cryptography.fernet import Fernet  # type: ignore
from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore

from ..config import get_settings
from ..models.oauth_token import OAuthToken
from ..models.user import User

logger = logging.getLogger(__name__)


class TokenCipher:
    def __init__(self, key: str | None):
        if not key:
            # generate ephemeral key (NOT for production)
            key = base64.urlsafe_b64encode(b"0" * 32).decode()
        self.fernet = Fernet(key)

    def enc(self, token: str) -> str:
        return self.fernet.encrypt(token.encode()).decode()

    def dec(self, token: str) -> str:
        return self.fernet.decrypt(token.encode()).decode()


class GoogleOAuthService:
    def __init__(self):
        self.settings = get_settings()
        self.cipher = TokenCipher(self.settings.token_encryption_key)

    async def exchange_code(self, code: str) -> dict[str, Any]:
        data = {
            "code": code,
            "client_id": self.settings.google_oauth_client_id,
            "client_secret": self.settings.google_oauth_client_secret,
            "redirect_uri": self.settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data=data)
            resp.raise_for_status()
            return resp.json()

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        data = {
            "client_id": self.settings.google_oauth_client_id,
            "client_secret": self.settings.google_oauth_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://oauth2.googleapis.com/token", data=data)
            resp.raise_for_status()
            return resp.json()

    async def store_tokens(self, db, user: User, token_payload: dict[str, Any]) -> OAuthToken:
        access_token = token_payload["access_token"]
        refresh_token = token_payload.get("refresh_token")
        expires_in = token_payload.get("expires_in")
        expiry = None
        if isinstance(expires_in, int | float):
            expiry = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

        row = OAuthToken(
            user_id=user.id,
            provider="google",
            access_token=self.cipher.enc(access_token),
            refresh_token=self.cipher.enc(refresh_token) if refresh_token else None,
            expiry=expiry,
        )
        db.add(row)
        await db.flush()
        return row

    def credentials_from_row(self, row: OAuthToken) -> Credentials:
        access_token = self.cipher.dec(row.access_token)
        refresh_token = self.cipher.dec(row.refresh_token) if row.refresh_token else None
        token_uri = "https://oauth2.googleapis.com/token"
        client_id = self.settings.google_oauth_client_id or ""
        client_secret = self.settings.google_oauth_client_secret or ""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=self.settings.google_oauth_scopes,
        )
        # Best-effort refresh if expired
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception:  # noqa: BLE001
            pass
        return creds
