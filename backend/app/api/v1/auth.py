from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.db import get_db
from app.models import Analyst
from app.rate_limit import login_rate_limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.strip().lower()
    ip = request.client.host if request.client else "unknown"
    analyst = None

    def authenticate():
        nonlocal analyst
        analyst = db.scalar(select(Analyst).where(func.lower(Analyst.email) == email))
        return analyst is not None and verify_password(form.password, analyst.password_hash)

    result = login_rate_limiter.attempt((ip, email), authenticate)
    if result is None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="Too many failed login attempts. Try again later.",
                            headers={"Retry-After": "60"})
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return {"access_token": create_access_token(analyst.email), "token_type": "bearer"}
