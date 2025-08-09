from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import get_settings
from ...db.session import get_db
from ...models.user import User
from ...services.google_oauth import GoogleOAuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
DbDep = Annotated[AsyncSession, Depends(get_db)]


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub: str | None = payload.get("sub")
        if sub is None:
            raise credentials_exception
        return sub
    except Exception as err:  # noqa: BLE001
        raise credentials_exception from err


@router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbDep
):
    # Minimal fake user lookup by username (email)
    res = await db.execute(select(User).where(User.email == form_data.username))
    user = res.scalars().first()
    if user is None:
        # Auto-create for demo
        user = User(email=form_data.username, name=form_data.username)
        db.add(user)
        await db.flush()
        await db.commit()
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def me(username: str = Depends(get_current_user)):
    return {"username": username}


@router.get("/login")
async def oauth_login() -> dict[str, str]:
    # Return frontend the URL to redirect user to Google's consent screen
    params = {
        "client_id": settings.google_oauth_client_id or "",
        "redirect_uri": settings.google_oauth_redirect_uri or "",
        "response_type": "code",
        "scope": " ".join(settings.google_oauth_scopes),
        "access_type": "offline",
        "prompt": "consent",
    }
    from urllib.parse import urlencode

    return {"url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"}


@router.get("/callback")
async def oauth_callback(code: str, db: DbDep):
    svc = GoogleOAuthService()
    token_payload = await svc.exchange_code(code)

    # For demo: bind to a dummy user by email from ID token (if present)
    email = None
    if id_token := token_payload.get("id_token"):
        try:
            decoded = jwt.decode(id_token, options={"verify_signature": False})
            email = decoded.get("email")
        except Exception:  # noqa: BLE001
            pass
    if not email:
        raise HTTPException(status_code=400, detail="No email in token")

    res = await db.execute(select(User).where(User.email == email))
    user = res.scalars().first()
    if user is None:
        user = User(email=email, name=email)
        db.add(user)
        await db.flush()

    await svc.store_tokens(db, user, token_payload)
    await db.commit()
    return {"status": "ok"}


@router.post("/logout")
async def logout():
    return {"status": "ok"}


