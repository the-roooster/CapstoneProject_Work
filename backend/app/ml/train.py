"""Train on stored features: python -m app.ml.train [--before YYYY-MM-DD]."""
import argparse
from datetime import date
import pandas as pd
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.features.columns import FEATURE_COLUMNS
from app.ml.calibration import Calibration
from app.ml.iforest import IsolationForestModel
from app.ml.registry import save
from app.models import Feature

def train(db, before=None):
    query = select(*(getattr(Feature, name) for name in FEATURE_COLUMNS)).order_by(Feature.user_id, Feature.date)
    if before is not None:
        query = query.where(Feature.date < before)
    frame = pd.DataFrame(db.execute(query).all(), columns=FEATURE_COLUMNS)
    if frame.empty:
        raise ValueError("No feature rows available for training")
    model = IsolationForestModel().fit(frame)
    calibration = Calibration.from_training_scores(model.score(frame), settings.MEDIUM_PCT, settings.HIGH_PCT)
    return save(model, calibration, FEATURE_COLUMNS)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=date.fromisoformat, default=None, help="exclusive cutoff date")
    args = parser.parse_args()
    with SessionLocal() as db:
        print(train(db, args.before))

if __name__ == "__main__":
    main()
