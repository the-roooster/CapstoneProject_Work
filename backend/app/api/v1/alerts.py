from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.v1.common import profile
from app.db import get_db
from app.explain.actions import suggested_action
from app.explain.summary import summarize
from app.features.columns import FEATURE_COLUMNS
from app.models import Feature, RiskScore, User
from app.schemas import AlertStatusUpdate

router = APIRouter(prefix="/alerts", tags=["alerts"])


def alert_dict(score, user):
    return {"score_id": score.score_id, "user_id": score.user_id, "full_name": user.full_name,
            "department": user.department, "date": score.date, "risk_score": score.risk_score,
            "risk_level": score.risk_level, "investigation_status": score.investigation_status,
            "top_reason": score.reasons[0].get("text") if score.reasons else None}


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    levels = ("Low", "Medium", "High")
    dist = {level: 0 for level in levels}
    for level, count in db.execute(select(RiskScore.risk_level, func.count()).group_by(RiskScore.risk_level)):
        dist[level] = count
    opened = {level: 0 for level in levels}
    for level, count in db.execute(select(RiskScore.risk_level, func.count()).where(
            RiskScore.investigation_status == "open", RiskScore.risk_level != "Low").group_by(RiskScore.risk_level)):
        opened[level] = count
    ranked = select(RiskScore.user_id, RiskScore.risk_score, RiskScore.risk_level, RiskScore.date,
                    func.row_number().over(partition_by=RiskScore.user_id,
                         order_by=(RiskScore.risk_score.desc(), RiskScore.date.desc())).label("rn")).subquery()
    top = db.execute(select(User.user_id, User.full_name, User.department, ranked.c.risk_score,
                            ranked.c.risk_level, ranked.c.date).join(ranked, ranked.c.user_id == User.user_id)
                     .where(ranked.c.rn == 1).order_by(ranked.c.risk_score.desc(), User.user_id).limit(6))
    return {"open_counts": opened, "distribution": dist,
            "top_users": [dict(row._mapping) for row in top], "total_user_days": sum(dist.values())}


@router.get("")
def alerts(level: str | None = None, department: str | None = None,
           status: str | None = None, start: date | None = Query(None, alias="from"),
           end: date | None = Query(None, alias="to"), sort: Literal["risk", "date"] = "risk",
           limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
           db: Session = Depends(get_db)):
    if start and end and start > end:
        raise HTTPException(422, "from must be on or before to")
    query = select(RiskScore, User).join(User, User.user_id == RiskScore.user_id).where(RiskScore.risk_level != "Low")
    if level:
        query = query.where(RiskScore.risk_level == level)
    if department:
        query = query.where(User.department == department)
    if status:
        query = query.where(RiskScore.investigation_status == status)
    if start:
        query = query.where(RiskScore.date >= start)
    if end:
        query = query.where(RiskScore.date <= end)
    order = (RiskScore.risk_score.desc(), RiskScore.date.desc()) if sort == "risk" else (RiskScore.date.desc(), RiskScore.risk_score.desc())
    query = query.order_by(*order, RiskScore.user_id).limit(limit).offset(offset)
    return [alert_dict(score, user) for score, user in db.execute(query)]


@router.get("/{score_id}")
def alert_detail(score_id: UUID, db: Session = Depends(get_db)):
    score = db.get(RiskScore, score_id)
    if score is None:
        raise HTTPException(404, "Alert not found")
    user = db.get(User, score.user_id)
    feature = db.scalar(select(Feature).where(Feature.user_id == score.user_id, Feature.date == score.date))
    return {**alert_dict(score, user), "anomaly_score": score.anomaly_score,
            "model_version": score.model_version, "scored_at": score.scored_at, "reasons": score.reasons,
            "features": {name: getattr(feature, name) for name in FEATURE_COLUMNS} if feature else None,
            "baseline": {"normal_login_start": user.normal_login_start, "normal_login_end": user.normal_login_end,
                         "normal_download_count": user.normal_download_count, "home_location": user.home_location,
                         "primary_device": user.primary_device},
            "suggested_action": suggested_action(score.risk_level)}


@router.patch("/{score_id}/status")
def update_status(score_id: UUID, body: AlertStatusUpdate, db: Session = Depends(get_db)):
    score = db.get(RiskScore, score_id)
    if score is None:
        raise HTTPException(404, "Alert not found")
    score.investigation_status = body.status
    db.commit()
    return {"score_id": score.score_id, "investigation_status": score.investigation_status}


@router.post("/{score_id}/summary")
def alert_summary(score_id: UUID, db: Session = Depends(get_db)):
    score = db.get(RiskScore, score_id)
    if score is None:
        raise HTTPException(404, "Alert not found")
    user = db.get(User, score.user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    feature = db.scalar(select(Feature).where(Feature.user_id == score.user_id, Feature.date == score.date))
    payload = {
        "employee": {name: getattr(user, name) for name in (
            "full_name", "role", "department", "normal_login_start", "normal_login_end",
            "normal_download_count", "home_location")},
        "date": score.date.isoformat(), "risk_score": score.risk_score,
        "risk_level": score.risk_level, "anomaly_score": score.anomaly_score,
        "reasons": [{"text": reason.get("text", ""), "severity": reason.get("severity")}
                    for reason in (score.reasons or [])],
        "features": {name: getattr(feature, name) for name in FEATURE_COLUMNS} if feature else None,
    }
    return summarize(payload)
