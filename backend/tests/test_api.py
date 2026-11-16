from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token, hash_password
from app.db import get_db
from app.main import app
from app.models import Analyst, Base, Event, Feature, RiskScore, SCHEMA, User
from app.api.v1 import jobs
from app.ml import registry


@pytest.fixture
def setup_client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
                           execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([Analyst(email="analyst@example.com", password_hash=hash_password("password")),
                    User(user_id="A", full_name="Alice", department="IT", role="Analyst",
                         primary_device="PC", home_location="Delhi"),
                    User(user_id="B", full_name="Bob", department="HR", role="Manager",
                         primary_device="PC2", home_location="Mumbai")])
        db.flush()
        db.add_all([
            Event(user_id="A", timestamp=datetime(2026, 1, 1, 4, tzinfo=timezone.utc),
                  activity_type="login", activity="login", device="PC", ip="1", location="Delhi"),
            Event(user_id="B", timestamp=datetime(2026, 1, 1, 5, tzinfo=timezone.utc),
                  activity_type="login", activity="login_failed", device="PC2", ip="2", location="Mumbai"),
            Feature(user_id="A", date=date(2026, 1, 1)),
            RiskScore(user_id="A", date=date(2026, 1, 1), anomaly_score=.8, risk_score=90,
                      risk_level="High", model_version="old", reasons=[{"text": "High risk"}]),
            RiskScore(user_id="A", date=date(2025, 12, 31), anomaly_score=.5, risk_score=10,
                      risk_level="Low", model_version="old"),
            RiskScore(user_id="B", date=date(2026, 1, 1), anomaly_score=.6, risk_score=50,
                      risk_level="Medium", model_version="old"),
        ])
        db.commit()
        score_id = str(db.query(RiskScore).filter_by(user_id="A", risk_level="High").one().score_id)
    def override_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    monkeypatch.setattr(registry, "MODEL_DIR", tmp_path / "models")
    with TestClient(app) as client:
        yield client, {"Authorization": f"Bearer {create_access_token('analyst@example.com')}"}, score_id
    app.dependency_overrides.clear()
    engine.dispose()


def test_auth_and_filters(setup_client):
    client, headers, score_id = setup_client
    for path in ("/api/v1/users", "/api/v1/events", "/api/v1/alerts", "/api/v1/meta", "/api/v1/jobs/missing"):
        assert client.get(path).status_code == 401
    assert client.post("/api/v1/score/run").status_code == 401
    assert client.patch(f"/api/v1/alerts/{score_id}/status", json={"status": "reviewed"}).status_code == 401
    assert client.get("/api/v1/health").status_code == 200
    assert [u["user_id"] for u in client.get("/api/v1/users?department=IT&level=High", headers=headers).json()] == ["A"]
    assert len(client.get("/api/v1/events?user_id=A&activity_type=login&from=2026-01-01&to=2026-01-01", headers=headers).json()) == 1
    assert len(client.get("/api/v1/events/by-ids?ids=1,2", headers=headers).json()) == 2
    assert client.get("/api/v1/events/by-ids?ids=" + ",".join(["1"] * 301), headers=headers).status_code == 422
    trend = client.get("/api/v1/events/trend?from=2026-01-01&to=2026-01-01", headers=headers)
    assert trend.status_code == 200
    assert trend.json()[0]["logins"] == trend.json()[0]["failed"] == 1
    alerts = client.get("/api/v1/alerts?level=High&department=IT&status=open", headers=headers).json()
    assert len(alerts) == 1 and alerts[0]["top_reason"] == "High risk"
    summary = client.get("/api/v1/alerts/summary", headers=headers).json()
    assert summary["total_user_days"] == 3
    assert summary["top_users"][0]["risk_score"] == 90
    response = client.patch(f"/api/v1/alerts/{score_id}/status", headers=headers, json={"status": "reviewed"})
    assert response.status_code == 200
    assert client.get(f"/api/v1/alerts/{score_id}", headers=headers).json()["investigation_status"] == "reviewed"


def test_score_twice_keeps_status(setup_client):
    client, headers, score_id = setup_client
    assert client.patch(f"/api/v1/alerts/{score_id}/status", headers=headers, json={"status": "reviewed"}).status_code == 200
    for _ in range(2):
        response = client.post("/api/v1/score/run", headers=headers)
        assert response.status_code == 200
        job = client.get("/api/v1/jobs/" + response.json()["job_id"], headers=headers).json()
        assert job["status"] == "done", job
    assert client.get(f"/api/v1/alerts/{score_id}", headers=headers).json()["investigation_status"] == "reviewed"
