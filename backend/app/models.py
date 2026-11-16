import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, MetaData, Text, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.features.columns import FEATURE_COLUMNS

SCHEMA = "sentinel"
json_type = JSON().with_variant(JSONB(), "postgresql")
id_type = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    full_name: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    normal_login_start: Mapped[int] = mapped_column(Integer, server_default=text("9"))
    normal_login_end: Mapped[int] = mapped_column(Integer, server_default=text("18"))
    normal_download_count: Mapped[int] = mapped_column(Integer, server_default=text("10"))
    home_location: Mapped[str] = mapped_column(Text)
    primary_device: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("activity_type IN ('login', 'file', 'usb', 'device')", name="ck_events_activity_type"),
        Index("ix_events_user_timestamp", "user_id", "timestamp"),
        Index("ix_events_timestamp", "timestamp"),
    )
    event_id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("sentinel.users.user_id", ondelete="CASCADE"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activity_type: Mapped[str] = mapped_column(Text)
    activity: Mapped[str] = mapped_column(Text)
    device: Mapped[str] = mapped_column(Text)
    ip: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    event_metadata: Mapped[dict] = mapped_column("metadata", json_type, default=dict, server_default=text("'{}'"))
    source_key: Mapped[str | None] = mapped_column(Text, unique=True)


class Feature(Base):
    __tablename__ = "features"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_features_user_date"),)
    feature_id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("sentinel.users.user_id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    first_login_hour: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    login_hour_deviation: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    off_hours_events: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    failed_logins: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    failed_login_ratio: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    downloads: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    download_ratio: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    download_zscore: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    mb_downloaded: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    uploads: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    deletes: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    renames: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    usb_events: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    new_usb_serial: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    new_device: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    distinct_devices: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    new_location: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))
    distinct_ips: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0"))


assert all(name in Feature.__table__.c for name in FEATURE_COLUMNS)


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_risk_scores_user_date"),
        CheckConstraint("investigation_status IN ('open', 'reviewed', 'escalated', 'dismissed')", name="ck_risk_scores_status"),
    )
    score_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("sentinel.users.user_id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    anomaly_score: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(Text)
    reasons: Mapped[list] = mapped_column(json_type, default=list, server_default=text("'[]'"))
    investigation_status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    model_version: Mapped[str] = mapped_column(Text)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Analyst(Base):
    __tablename__ = "analysts"
    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
