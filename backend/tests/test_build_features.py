import os
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["APP_TZ"] = "Asia/Kolkata"

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.features.build_features import build_features, compute_features
from app.features.columns import FEATURE_COLUMNS
from app.models import Base, Event, Feature, SCHEMA, User


def inputs():
    user = {"user_id": "A", "normal_login_start": 9, "normal_login_end": 18,
            "normal_download_count": 10, "primary_device": "PC", "home_location": "Delhi"}
    local = timezone(timedelta(hours=5, minutes=30))
    rows = []
    for day in range(21):
        stamp = datetime(2026, 1, 1, 9 if day < 20 else 2, tzinfo=local) + timedelta(days=day)
        device = "PC" if day < 20 else "NEW"
        def add(activity, metadata=None):
            rows.append({"user_id": "A", "timestamp": stamp, "activity": activity, "device": device,
                         "ip": "1.1.1.1", "location": "Delhi", "metadata": metadata or {}})
        add("login")
        for _ in range(10 if day < 20 else 120):
            add("file_download", {"size_kb": 1024})
        if day == 20:
            add("usb_connect", {"serial": "NEW-USB"})
    return user, rows


def test_features_and_database_upsert():
    user, rows = inputs()
    events = pd.DataFrame(rows)
    users = pd.DataFrame([user])
    original = events.copy(deep=True)
    features = compute_features(events, users)
    pd.testing.assert_frame_equal(events, original)
    assert tuple(features.columns) == ("user_id", "date", *FEATURE_COLUMNS)
    assert len(features) == 21
    normal = features.iloc[:20]
    assert (normal["first_login_hour"] == 9).all()
    assert (normal["download_ratio"] == 1).all()
    assert (normal["new_device"] == 0).all()
    anomaly = features.iloc[-1]
    assert anomaly["date"] == date(2026, 1, 21)
    assert anomaly["first_login_hour"] == 2
    assert anomaly["download_ratio"] > 8
    assert anomaly["new_device"] == anomaly["usb_events"] == anomaly["new_usb_serial"] == 1
    assert anomaly["mb_downloaded"] == 120

    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(**user, full_name="A", department="IT", role="analyst"))
        session.flush()
        for row in rows:
            record = dict(row)
            record["timestamp"] = record["timestamp"].astimezone(timezone.utc)
            record["event_metadata"] = record.pop("metadata")
            record["activity_type"] = {"login": "login", "file_download": "file", "usb_connect": "usb"}[record["activity"]]
            session.add(Event(**record))
        session.commit()
        build_features(session)
        assert session.scalar(select(func.count()).select_from(Feature)) == 21
        subset = build_features(session, start=date(2026, 1, 21), end=date(2026, 1, 21), user_ids=["A"])
        assert subset.iloc[0]["download_ratio"] == anomaly["download_ratio"]
        assert session.scalar(select(func.count()).select_from(Feature)) == 21


def test_history_and_timezone_boundary():
    user, rows = inputs()
    rows = rows[:11]
    # This is 02:00 on the following day in Kolkata.
    rows.append({"user_id": "A", "timestamp": "2026-01-01T20:30:00Z", "activity": "login_failed",
                 "device": "PC", "ip": "1.1.1.1", "location": "Delhi", "metadata": {}})
    result = compute_features(pd.DataFrame(rows), pd.DataFrame([user]))
    second = result.iloc[1]
    assert second["date"] == date(2026, 1, 2)
    assert second["first_login_hour"] == 9
    assert second["failed_logins"] == second["failed_login_ratio"] == 1
    assert second["off_hours_events"] == 1
