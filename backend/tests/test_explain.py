import os
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.explain.actions import suggested_action
from app.explain.rules import explain
from app.explain.run import explain_all
from app.models import Base, Event, Feature, RiskScore, SCHEMA, User


def fixture():
    user = {"user_id": "E1", "normal_login_start": 9, "normal_login_end": 18,
            "normal_download_count": 10, "home_location": "Pune", "primary_device": "WS-1"}
    feat = {"date": date(2026, 1, 21), "first_login_hour": 2, "login_hour_deviation": 7,
            "off_hours_events": 122, "failed_logins": 0, "downloads": 120,
            "download_ratio": 12.0, "download_zscore": 110, "usb_events": 1,
            "new_usb_serial": 1, "new_device": 1, "new_location": 0, "deletes": 0}
    stamp = datetime(2026, 1, 20, 20, 40, tzinfo=timezone.utc)  # 02:10 Kolkata
    events = [{"event_id": 1, "timestamp": stamp, "activity": "login", "device": "LAPTOP-X", "location": "Pune"}]
    events.extend({"event_id": i + 2, "timestamp": stamp, "activity": "file_download",
                   "device": "LAPTOP-X", "location": "Pune"} for i in range(120))
    events.append({"event_id": 122, "timestamp": stamp + timedelta(hours=1), "activity": "usb_connect",
                   "device": "LAPTOP-X", "location": "Pune"})
    return user, feat, events


def test_scenario_and_normal_day():
    user, feat, events = fixture()
    reasons = explain(user, feat, {"download_mean": 10}, events)
    codes = {r["code"] for r in reasons}
    assert {"LATE_LOGIN", "OFF_HOURS", "MASS_DOWNLOAD", "FIRST_USB", "NEW_DEVICE",
            "NEW_USB_SERIAL", "DOWNLOAD_ZSCORE"} <= codes
    assert next(r["text"] for r in reasons if r["code"] == "LATE_LOGIN") == "Login at 02:10, outside normal hours (9-18)"
    assert all(len(r["event_ids"]) <= 200 for r in reasons)
    assert [r["severity"] for r in reasons] == sorted((r["severity"] for r in reasons), reverse=True)
    normal = {**feat, "off_hours_events": 0, "login_hour_deviation": 0, "downloads": 10,
              "download_ratio": 1, "download_zscore": 0, "usb_events": 0, "new_usb_serial": 0,
              "new_device": 0}
    normal_events = [{"event_id": 1, "timestamp": datetime(2026, 1, 21, 4, tzinfo=timezone.utc),
                      "activity": "login", "device": "WS-1", "location": "Pune"}]
    assert explain(user, normal, {"download_mean": 10}, normal_events) == []
    assert suggested_action("Low") == "No action needed. Keep monitoring."


def test_usb_lookback():
    user, feat, events = fixture()
    now = events[-1]["timestamp"]
    old = {"event_id": 500, "activity": "usb_connect", "timestamp": now - timedelta(days=10),
           "device": "WS-1", "location": "Pune"}
    assert "FIRST_USB" not in {r["code"] for r in explain(user, feat, {}, events + [old])}
    old["timestamp"] = now - timedelta(days=100)
    reason = next(r for r in explain(user, feat, {}, events + [old]) if r["code"] == "FIRST_USB")
    assert "90 days" in reason["text"]


def test_runner_preserves_scores():
    user, feat, events = fixture()
    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(**user, full_name="A", department="IT", role="analyst"))
        session.flush()
        for event in events:
            session.add(Event(user_id="E1", timestamp=event["timestamp"], activity=event["activity"],
                              activity_type={"login": "login", "file_download": "file", "usb_connect": "usb"}[event["activity"]],
                              device=event["device"], location=event["location"], ip="10.0.0.1"))
        session.add(Feature(user_id="E1", **feat))
        session.add(RiskScore(user_id="E1", date=feat["date"], anomaly_score=.9,
                              risk_score=84, risk_level="High", model_version="v1",
                              investigation_status="reviewed"))
        session.commit()
        assert explain_all(session) == 1
        score = session.query(RiskScore).one()
        assert (score.risk_score, score.risk_level, score.investigation_status) == (84, "High", "reviewed")
        assert {"MASS_DOWNLOAD", "FIRST_USB", "NEW_DEVICE"} <= {r["code"] for r in score.reasons}
        assert explain_all(session, since="2026-01-22") == 0


def test_event_id_limit():
    user, feat, events = fixture()
    template = events[1]
    events.extend({**template, "event_id": 1000 + i} for i in range(250))
    reasons = explain(user, feat, {"download_mean": 10}, events)
    mass = next(reason for reason in reasons if reason["code"] == "MASS_DOWNLOAD")
    assert len(mass["event_ids"]) == 200
