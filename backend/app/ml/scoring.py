from datetime import date, datetime, timezone
import uuid
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.features.columns import FEATURE_COLUMNS
from app.ml.registry import load_latest
from app.models import Feature, RiskScore

def score_features(db, since=None):
    """Score user-days using the latest training calibration; since is inclusive."""
    artifact = load_latest()
    columns = artifact["feature_columns"]
    if list(columns) != list(FEATURE_COLUMNS):
        raise ValueError("Saved feature columns do not match current columns; retrain the model")
    if isinstance(since, str):
        since = date.fromisoformat(since)
    query = select(Feature.user_id, Feature.date, *(getattr(Feature, name) for name in columns))
    if since is not None:
        query = query.where(Feature.date >= since)
    rows = db.execute(query.order_by(Feature.user_id, Feature.date)).all()
    if not rows:
        return 0
    frame = pd.DataFrame(rows, columns=["user_id", "date", *columns])
    scores = artifact["model"].score(frame[columns])
    calibration = artifact["calibration"]
    now = datetime.now(timezone.utc)
    records = [{"score_id": uuid.uuid4(), "user_id": row.user_id, "date": row.date,
                "anomaly_score": float(score), "risk_score": calibration.risk_score(float(score)),
                "risk_level": calibration.level(float(score)), "model_version": artifact["version"],
                "scored_at": now} for row, score in zip(rows, scores, strict=True)]
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise ValueError(f"Unsupported database: {dialect}")
    for i in range(0, len(records), 400):
        stmt = insert(RiskScore.__table__).values(records[i:i + 400])
        stmt = stmt.on_conflict_do_update(index_elements=["user_id", "date"],
            set_={name: getattr(stmt.excluded, name) for name in
                  ("anomaly_score", "risk_score", "risk_level", "model_version", "scored_at")})
        db.execute(stmt)
    db.commit()
    return len(records)
