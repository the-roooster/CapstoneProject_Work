"""Persist rule explanations without modifying model scores."""
from collections import defaultdict, deque
from datetime import date

from sqlalchemy import select

from app.explain.rules import explain
from app.models import Event, Feature, RiskScore, User


def explain_all(db, since=None):
    """Update reasons for Medium and High risk user-days; since is inclusive."""
    if isinstance(since, str):
        since = date.fromisoformat(since)
    query = (select(RiskScore, Feature, User)
             .join(Feature, (Feature.user_id == RiskScore.user_id) & (Feature.date == RiskScore.date))
             .join(User, User.user_id == RiskScore.user_id)
             .where(RiskScore.risk_level.in_(("Medium", "High")))
             .order_by(RiskScore.user_id, RiskScore.date))
    if since is not None:
        query = query.where(RiskScore.date >= since)
    rows = db.execute(query).all()
    if not rows:
        return 0
    ids = sorted({score.user_id for score, _, _ in rows})
    by_user = defaultdict(list)
    feature_history = defaultdict(list)
    for i in range(0, len(ids), 500):
        batch = ids[i:i + 500]
        for event in db.scalars(select(Event).where(Event.user_id.in_(batch)).order_by(Event.timestamp)):
            by_user[event.user_id].append(event)
        for feature in db.scalars(select(Feature).where(Feature.user_id.in_(batch)).order_by(Feature.user_id, Feature.date)):
            feature_history[feature.user_id].append(feature)

    for score, feature, user in rows:
        prior = deque((f.downloads for f in feature_history[score.user_id] if f.date < score.date), maxlen=14)
        if prior:
            mean = sum(prior) / len(prior)
        elif feature.download_ratio:
            mean = feature.downloads / feature.download_ratio
        else:
            mean = user.normal_download_count
        score.reasons = explain(user, feature, {"download_mean": mean}, by_user[score.user_id])
    db.commit()
    return len(rows)
