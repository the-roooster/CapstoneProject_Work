from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.v1.common import profile
from app.db import get_db
from app.models import Event, RiskScore, User
from app.schemas import UserSummary

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserSummary])
def users(department: str | None = None, level: str | None = None, db: Session = Depends(get_db)):
    ranked = select(RiskScore.user_id, RiskScore.risk_level, RiskScore.risk_score,
                    func.row_number().over(partition_by=RiskScore.user_id,
                        order_by=(RiskScore.date.desc(), RiskScore.scored_at.desc(), RiskScore.score_id.desc())).label("rn")).subquery()
    query = (select(User, ranked.c.risk_level, ranked.c.risk_score)
             .outerjoin(ranked, (ranked.c.user_id == User.user_id) & (ranked.c.rn == 1)))
    if department:
        query = query.where(User.department == department)
    if level:
        query = query.where(ranked.c.risk_level == level)
    return [{**profile(user), "risk_level": risk_level, "risk_score": risk_score}
            for user, risk_level, risk_score in db.execute(query.order_by(User.user_id))]


@router.get("/{user_id}")
def user_detail(user_id: str, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    history = db.scalars(select(RiskScore).where(RiskScore.user_id == user_id).order_by(RiskScore.date.desc())).all()
    devices = list(db.scalars(select(Event.device).where(Event.user_id == user_id).distinct().order_by(Event.device)))
    return {**profile(user), "baseline": {"normal_login_start": user.normal_login_start,
             "normal_login_end": user.normal_login_end, "normal_download_count": user.normal_download_count,
             "home_location": user.home_location, "primary_device": user.primary_device},
            "risk_history": [{"date": r.date, "risk_score": r.risk_score, "risk_level": r.risk_level} for r in history],
            "devices": devices,
            "recent_anomalies": [{"score_id": r.score_id, "date": r.date, "risk_score": r.risk_score,
                                  "risk_level": r.risk_level} for r in history if r.risk_level != "Low"][:20]}
