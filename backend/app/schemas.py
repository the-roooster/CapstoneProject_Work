from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["Low", "Medium", "High"]
InvestigationStatus = Literal["open", "reviewed", "escalated", "dismissed"]


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: str
    full_name: str
    department: str
    role: str
    normal_login_start: int
    normal_login_end: int
    normal_download_count: int
    home_location: str
    primary_device: str
    created_at: datetime


class UserSummary(UserProfile):
    risk_level: RiskLevel | None = None
    risk_score: int | None = None


class EventOut(BaseModel):
    event_id: int
    user_id: str
    timestamp: datetime
    activity_type: str
    activity: str
    device: str
    ip: str
    location: str
    metadata: dict[str, Any]
    source_key: str | None = None


class AlertStatusUpdate(BaseModel):
    status: InvestigationStatus


class JobCreated(BaseModel):
    job_id: str


class JobOut(BaseModel):
    status: Literal["running", "done", "error"]
    report: Any = None


class TrendRow(BaseModel):
    date: date
    logins: int
    files: int
    usb: int
    failed: int


class LocationRow(BaseModel):
    location: str
    logins: int
    unusual: int
    users: list[str]
