from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Analyst

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False


def create_access_token(email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": expires}, settings.JWT_SECRET, algorithm="HS256")


def get_current_analyst(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Analyst:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                 detail="Invalid or expired authentication credentials",
                                 headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"],
                             options={"require_exp": True, "require_sub": True})
        email = payload.get("sub")
        if not isinstance(email, str) or not email:
            raise unauthorized
    except JWTError:
        raise unauthorized
    analyst = db.scalar(select(Analyst).where(Analyst.email == email))
    if analyst is None:
        raise unauthorized
    return analyst
