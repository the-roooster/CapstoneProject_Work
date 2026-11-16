from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.columns import FEATURE_COLUMNS
from app.models import Analyst, Base, Event, Feature, RiskScore, SCHEMA, User


def test_models_and_unique_constraints():
    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    day = date(2026, 1, 1)
    with Session(engine) as session:
        session.add(User(user_id="A", full_name="A", department="IT", role="analyst",
                         home_location="Delhi", primary_device="PC"))
        session.flush()
        session.add_all([
            Event(user_id="A", timestamp=datetime.now(timezone.utc), activity_type="login",
                  activity="login", device="PC", ip="127.0.0.1", location="Delhi", source_key="source"),
            Feature(user_id="A", date=day, **{name: 1.0 for name in FEATURE_COLUMNS}),
            RiskScore(user_id="A", date=day, anomaly_score=0.5, risk_score=50,
                      risk_level="Medium", model_version="v1"),
            Analyst(email="analyst@example.com", password_hash="hash"),
        ])
        session.commit()
        assert session.query(Event).one().event_metadata == {}
        assert session.query(RiskScore).one().reasons == []
        assert session.query(RiskScore).one().investigation_status == "open"

        duplicates = [
            User(user_id="A", full_name="A", department="IT", role="analyst", home_location="Delhi", primary_device="PC"),
            Event(user_id="A", timestamp=datetime.now(timezone.utc), activity_type="login",
                  activity="login", device="PC", ip="127.0.0.1", location="Delhi", source_key="source"),
            Feature(user_id="A", date=day),
            RiskScore(user_id="A", date=day, anomaly_score=0.1, risk_score=1,
                      risk_level="Low", model_version="v1"),
            Analyst(email="analyst@example.com", password_hash="other"),
        ]
        for duplicate in duplicates:
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.flush()
            session.rollback()
