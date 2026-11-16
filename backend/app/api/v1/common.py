from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_
from app.config import settings
from app.models import Event


def bounds(query, start: date | None, end: date | None):
    if start and end and start > end:
        raise HTTPException(422, "from must be on or before to")
    tz = ZoneInfo(settings.APP_TZ)
    if start:
        query = query.where(Event.timestamp >= datetime.combine(start, time.min, tz).astimezone(timezone.utc))
    if end:
        query = query.where(Event.timestamp < datetime.combine(end + timedelta(days=1), time.min, tz).astimezone(timezone.utc))
    return query


def event_dict(event):
    return {"event_id": event.event_id, "user_id": event.user_id, "timestamp": event.timestamp,
            "activity_type": event.activity_type, "activity": event.activity, "device": event.device,
            "ip": event.ip, "location": event.location, "metadata": event.event_metadata,
            "source_key": event.source_key}


def profile(user):
    return {name: getattr(user, name) for name in (
        "user_id", "full_name", "department", "role", "normal_login_start", "normal_login_end",
        "normal_download_count", "home_location", "primary_device", "created_at")}
