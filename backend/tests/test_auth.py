from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import router
from app.auth import get_current_analyst, hash_password
from app.config import Settings, settings
from app.db import get_db
from app.models import Analyst, Base, SCHEMA


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
                           execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Analyst(email="analyst@example.com", password_hash=hash_password("correct-password")))
        db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    @app.get("/protected")
    def protected(analyst: Analyst = Depends(get_current_analyst)):
        return {"email": analyst.email}

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def test_login_and_protected(client):
    url = "/api/v1/auth/login"
    response = client.post(url, data={"username": "analyst@example.com", "password": "correct-password"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    token = response.json()["access_token"]
    assert client.post(url, data={"username": "analyst@example.com", "password": "wrong"}).status_code == 401
    assert client.post(url, data={"username": "missing@example.com", "password": "wrong"}).status_code == 401
    assert client.get("/protected").status_code == 401
    assert client.get("/protected", headers={"Authorization": "Bearer garbage"}).status_code == 401
    expired = jwt.encode({"sub": "analyst@example.com", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         settings.JWT_SECRET, algorithm="HS256")
    assert client.get("/protected", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    assert client.get("/protected", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    missing_exp = jwt.encode({"sub": "analyst@example.com"}, settings.JWT_SECRET, algorithm="HS256")
    assert client.get("/protected", headers={"Authorization": f"Bearer {missing_exp}"}).status_code == 401


def test_secret_required_outside_tests():
    with pytest.raises(ValidationError, match="JWT_SECRET must be at least 32 characters"):
        Settings(DATABASE_URL="sqlite://", JWT_SECRET="short", TESTING=False, _env_file=None)
    assert Settings(DATABASE_URL="sqlite://", JWT_SECRET="short", TESTING=True, _env_file=None).JWT_SECRET == "short"


def test_seed_is_idempotent():
    from scripts.seed_analyst import seed_analyst

    engine = create_engine("sqlite://", poolclass=StaticPool,
                           execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert seed_analyst(db, "demo@example.com", "demo-password") is True
        assert seed_analyst(db, "demo@example.com", "different-password") is False
        assert db.query(Analyst).count() == 1
    engine.dispose()
