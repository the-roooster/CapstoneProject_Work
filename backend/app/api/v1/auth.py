from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.db import get_db
from app.models import Analyst

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    analyst = db.scalar(select(Analyst).where(Analyst.email == form.username))
    if analyst is None or not verify_password(form.password, analyst.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return {"access_token": create_access_token(analyst.email), "token_type": "bearer"}
