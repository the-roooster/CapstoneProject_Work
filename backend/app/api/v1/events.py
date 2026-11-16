from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from app.api.v1.common import bounds, event_dict
from app.config import settings
from app.db import get_db
from app.models import Event, User
from app.schemas import EventOut, LocationRow, TrendRow

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/by-ids", response_model=list[EventOut])
def by_ids(ids: str, db: Session = Depends(get_db)):
    try:
        parts = ids.split(",")
        if len(parts) > 300 or not all(part.strip() for part in parts):
            raise ValueError()
        values = [int(part) for part in parts]
        if any(value < 1 for value in values):
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "ids must contain 1–300 positive integers")
    return [event_dict(event) for event in db.scalars(select(Event).where(Event.event_id.in_(values)).order_by(Event.timestamp, Event.event_id))]


@router.get("/trend", response_model=list[TrendRow])
def trend(start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"), db: Session = Depends(get_db)):
    if db.get_bind().dialect.name == "postgresql":
        day = func.date(func.timezone(settings.APP_TZ, Event.timestamp))
    else:
        # SQLite does not ship IANA timezone rules; install a per-connection SQL function.
        raw = db.connection().connection.driver_connection
        tz = ZoneInfo(settings.APP_TZ)
        def local_day(value):
            if value is None:
                return None
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return stamp.astimezone(tz).date().isoformat()
        raw.create_function("app_local_day", 1, local_day, deterministic=True)
        day = func.app_local_day(Event.timestamp)
    count = lambda condition: func.sum(case((condition, 1), else_=0))
    query = select(day.label("date"), count(Event.activity == "login").label("logins"),
                   count(Event.activity_type == "file").label("files"),
                   count(Event.activity_type == "usb").label("usb"),
                   count(Event.activity == "login_failed").label("failed"))
    query = bounds(query, start, end).group_by(day).order_by(day)
    return [dict(row._mapping) for row in db.execute(query)]


@router.get("/locations", response_model=list[LocationRow])
def locations(db: Session = Depends(get_db)):
    query = (select(Event.location, func.count().label("logins"),
                    func.sum(case((Event.location != User.home_location, 1), else_=0)).label("unusual"))
             .join(User, User.user_id == Event.user_id).where(Event.activity == "login")
             .group_by(Event.location).order_by(Event.location))
    names = {}
    for location, name in db.execute(select(Event.location, User.full_name).join(User, User.user_id == Event.user_id)
                                     .where(Event.activity == "login").distinct().order_by(Event.location, User.full_name)):
        names.setdefault(location, []).append(name)
    return [{"location": loc, "logins": count, "unusual": unusual, "users": names.get(loc, [])[:10]}
            for loc, count, unusual in db.execute(query)]


@router.get("", response_model=list[EventOut])
def events(user_id: str | None = None, start: date | None = Query(None, alias="from"),
           end: date | None = Query(None, alias="to"), activity_type: str | None = None,
           limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0),
           db: Session = Depends(get_db)):
    query = bounds(select(Event), start, end)
    if user_id:
        query = query.where(Event.user_id == user_id)
    if activity_type:
        query = query.where(Event.activity_type == activity_type)
    return [event_dict(event) for event in db.scalars(query.order_by(Event.timestamp.desc(), Event.event_id.desc()).limit(limit).offset(offset))]
