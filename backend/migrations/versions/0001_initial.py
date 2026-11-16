"""Initial isolated backend schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

schema = "sentinel"
json_type = sa.JSON().with_variant(JSONB(), "postgresql")
id_type = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade():
    if op.get_context().dialect.name == "postgresql":
        op.execute(sa.schema.CreateSchema(schema, if_not_exists=True))
    op.create_table("users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("normal_login_start", sa.Integer(), nullable=False, server_default="9"),
        sa.Column("normal_login_end", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("normal_download_count", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("home_location", sa.Text(), nullable=False),
        sa.Column("primary_device", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=schema)
    op.create_table("events",
        sa.Column("event_id", id_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("sentinel.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("activity", sa.Text(), nullable=False),
        sa.Column("device", sa.Text(), nullable=False),
        sa.Column("ip", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("metadata", json_type, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source_key", sa.Text(), unique=True),
        sa.CheckConstraint("activity_type IN ('login', 'file', 'usb', 'device')", name="ck_events_activity_type"),
        schema=schema)
    op.create_index("ix_events_user_timestamp", "events", ["user_id", "timestamp"], schema=schema)
    op.create_index("ix_events_timestamp", "events", ["timestamp"], schema=schema)
    op.create_table("features",
        sa.Column("feature_id", id_type, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("sentinel.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("first_login_hour", sa.Float(), nullable=False, server_default="0"),
        sa.Column("login_hour_deviation", sa.Float(), nullable=False, server_default="0"),
        sa.Column("off_hours_events", sa.Float(), nullable=False, server_default="0"),
        sa.Column("failed_logins", sa.Float(), nullable=False, server_default="0"),
        sa.Column("failed_login_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("downloads", sa.Float(), nullable=False, server_default="0"),
        sa.Column("download_ratio", sa.Float(), nullable=False, server_default="0"),
        sa.Column("download_zscore", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mb_downloaded", sa.Float(), nullable=False, server_default="0"),
        sa.Column("uploads", sa.Float(), nullable=False, server_default="0"),
        sa.Column("deletes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("renames", sa.Float(), nullable=False, server_default="0"),
        sa.Column("usb_events", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_usb_serial", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_device", sa.Float(), nullable=False, server_default="0"),
        sa.Column("distinct_devices", sa.Float(), nullable=False, server_default="0"),
        sa.Column("new_location", sa.Float(), nullable=False, server_default="0"),
        sa.Column("distinct_ips", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "date", name="uq_features_user_date"),
        schema=schema)
    op.create_table("risk_scores",
        sa.Column("score_id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("sentinel.users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=False),
        sa.Column("reasons", json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("investigation_status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "date", name="uq_risk_scores_user_date"),
        sa.CheckConstraint("investigation_status IN ('open', 'reviewed', 'escalated', 'dismissed')", name="ck_risk_scores_status"),
        schema=schema)
    op.create_table("analysts",
        sa.Column("id", id_type, primary_key=True, autoincrement=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=schema)


def downgrade():
    for name in ("analysts", "risk_scores", "features", "events", "users"):
        op.drop_table(name, schema=schema)
