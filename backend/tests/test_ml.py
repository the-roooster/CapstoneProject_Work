from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.features.columns import FEATURE_COLUMNS
from app.ml.calibration import Calibration
from app.ml.iforest import IsolationForestModel
from app.ml import registry, scoring
from app.models import Base, Feature, RiskScore, SCHEMA, User


def training_frame():
    rng = np.random.default_rng(42)
    return pd.DataFrame(rng.normal(0, 1, (256, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)


def test_model_determinism_calibration_and_registry(tmp_path):
    X = training_frame()
    first = IsolationForestModel().fit(X)
    second = IsolationForestModel().fit(X)
    scores = first.score(X)
    np.testing.assert_array_equal(scores, second.score(X))
    calibration = Calibration.from_training_scores(scores)
    extreme = pd.DataFrame([[1000.0] * len(FEATURE_COLUMNS)], columns=FEATURE_COLUMNS)
    extreme_score = float(first.score(extreme)[0])
    assert extreme_score > max(scores)
    assert calibration.level(extreme_score) == "High"
    samples = np.linspace(min(scores), max(extreme_score, calibration.hi), 1000)
    levels = [{"Low": 0, "Medium": 1, "High": 2}[calibration.level(s)] for s in samples]
    assert levels == sorted(levels)
    risks = [calibration.risk_score(s) for s in samples]
    assert risks == sorted(risks)
    assert calibration.risk_score(calibration.med_cut) == 40
    assert calibration.risk_score(calibration.high_cut) == 70
    version = registry.save(first, calibration, FEATURE_COLUMNS, tmp_path)
    artifact = registry.load_latest(tmp_path)
    assert artifact["version"] == version
    assert artifact["feature_columns"] == list(FEATURE_COLUMNS)
    np.testing.assert_array_equal(scores, artifact["model"].score(X))
    assert artifact["calibration"] == calibration


def test_no_model(tmp_path):
    with pytest.raises(FileNotFoundError, match="No trained model"):
        registry.load_latest(tmp_path)


def test_rescoring_preserves_investigation(tmp_path, monkeypatch):
    X = training_frame()
    model = IsolationForestModel().fit(X)
    calibration = Calibration.from_training_scores(model.score(X))
    registry.save(model, calibration, FEATURE_COLUMNS, tmp_path)
    monkeypatch.setattr(scoring, "load_latest", lambda: registry.load_latest(tmp_path))
    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(User(user_id="A", full_name="A", department="IT", role="analyst",
                         home_location="Delhi", primary_device="PC"))
        session.flush()
        values = dict(zip(FEATURE_COLUMNS, X.iloc[0].tolist()))
        session.add(Feature(user_id="A", date=date(2026, 1, 1), **values))
        session.commit()
        assert scoring.score_features(session) == 1
        score = session.query(RiskScore).one()
        score.investigation_status = "reviewed"
        score.reasons = [{"code": "MANUAL"}]
        original_id = score.score_id
        session.commit()
        assert scoring.score_features(session) == 1
        session.expire_all()
        score = session.query(RiskScore).one()
        assert score.score_id == original_id
        assert score.investigation_status == "reviewed"
        assert score.reasons == [{"code": "MANUAL"}]
        assert scoring.score_features(session, since="2026-01-02") == 0
