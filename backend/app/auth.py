from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from .config import settings
from .db import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd.verify(password, hashed)


def issue_token(user: User) -> str:
    now = datetime.now(tz=timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "username": user.username,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=settings.jwt_ttl_seconds)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_alg,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
