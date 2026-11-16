from datetime import date
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.v1.alerts import alert_summary
from app.explain import summary
from app.models import Base, Feature, RiskScore, SCHEMA, User


@pytest.fixture
def alert_db():
    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(user_id="A", full_name="Alice", department="IT", role="Analyst",
                    home_location="Delhi", primary_device="PC"))
        db.flush()
        db.add(Feature(user_id="A", date=date(2026, 1, 1), downloads=100))
        score = RiskScore(user_id="A", date=date(2026, 1, 1), risk_score=80,
                          risk_level="High", anomaly_score=0.8, model_version="v1",
                          reasons=[{"text": "Mass download", "severity": 35, "event_ids": [1]}])
        db.add(score)
        db.commit()
        yield db, score.score_id
    engine.dispose()


def test_provider_none_returns_deterministic_template(alert_db, monkeypatch):
    db, score_id = alert_db
    monkeypatch.setenv("LLM_PROVIDER", "none")
    first = alert_summary(score_id, db)
    assert first == alert_summary(score_id, db)
    assert first["source"] == "template"
    assert "Mass download" in first["summary"]


def test_provider_error_falls_back(alert_db, monkeypatch):
    db, score_id = alert_db
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    def fail(*args, **kwargs):
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(summary.httpx, "post", fail)
    result = alert_summary(score_id, db)
    assert result["source"] == "template"
    assert "Mass download" in result["summary"]


def test_provider_receives_payload_and_prompt(alert_db, monkeypatch):
    db, score_id = alert_db
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    def post(url, **kwargs):
        import json
        assert kwargs["json"]["instructions"] == summary.SYSTEM_PROMPT
        assert kwargs["json"]["model"] == "test-model"
        payload = json.loads(kwargs["json"]["input"])
        assert payload["employee"]["normal_download_count"] == 10
        assert payload["reasons"] == [{"text": "Mass download", "severity": 35}]
        assert payload["features"]["downloads"] == 100
        return httpx.Response(200, json={"output": [{"content": [{"type": "output_text", "text": "Review the event."}]}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(summary.httpx, "post", post)
    assert alert_summary(score_id, db) == {"summary": "Review the event.", "source": "llm"}
