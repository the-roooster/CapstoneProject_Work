"""Compute user-day features and persist them without changing source events."""

import json
import math
from collections import Counter, deque
from datetime import date, datetime

import pandas as pd
from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.features.columns import FEATURE_COLUMNS
from app.models import Event, Feature, User

OUTPUT_COLUMNS = ("user_id", "date", *FEATURE_COLUMNS)


def _metadata(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _present(value):
    return isinstance(value, str) and bool(value.strip())


def _size(metadata):
    try:
        value = float(metadata.get("size_kb", 0) or 0)
        return value if math.isfinite(value) else 0.0
    except (ValueError, TypeError):
        return 0.0


def compute_features(events_df: pd.DataFrame, users_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate features using only inputs and configured timezone, without mutating either.

    Rolling history is the prior 14 active user-days, with population standard
    deviation; users without history use their configured download baseline.
    Naive timestamps are interpreted as UTC.
    """
    if events_df.empty or users_df.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    events = events_df.copy()
    users = users_df.set_index("user_id", verify_integrity=True)
    events = events[events["user_id"].isin(users.index)].copy()
    if events.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    timestamps = pd.to_datetime(events["timestamp"], utc=True, errors="raise").dt.tz_convert(settings.APP_TZ)
    events["_date"] = timestamps.dt.date
    events["_hour"] = timestamps.dt.hour
    events["_timestamp"] = timestamps
    if "metadata" not in events:
        events["metadata"] = [{} for _ in range(len(events))]
    events["_metadata"] = events["metadata"].map(_metadata)
    events = events.sort_values(["user_id", "_timestamp"], kind="stable")
    result = []

    for user_id, user_events in events.groupby("user_id", sort=True):
        user = users.loc[user_id]
        start, end = int(user["normal_login_start"]), int(user["normal_login_end"])
        baseline = float(user["normal_download_count"])
        seen_devices = {user["primary_device"]} if _present(user["primary_device"]) else set()
        seen_locations = {user["home_location"]} if _present(user["home_location"]) else set()
        seen_serials = set()
        previous_downloads = deque(maxlen=14)
        for day, group in user_events.groupby("_date", sort=True):
            counts = Counter(group["activity"])
            successful = group[group["activity"] == "login"]
            first_hour = int(successful["_hour"].min()) if not successful.empty else start
            failed = counts["login_failed"]
            downloads = counts["file_download"]
            history = list(previous_downloads)
            mean = sum(history) / len(history) if history else baseline
            std = math.sqrt(sum((value - mean) ** 2 for value in history) / len(history)) if history else 0.0
            devices = {value for value in group["device"] if _present(value)}
            locations = {value for value in group["location"] if _present(value)}
            ips = {value for value in group["ip"] if _present(value)}
            new_serial = 0
            # Track serials on both connection and removal events in time order.
            for _, event in group.iterrows():
                if event["activity"] not in ("usb_connect", "usb_disconnect"):
                    continue
                serial = event["_metadata"].get("serial")
                if _present(serial):
                    if event["activity"] == "usb_connect" and serial not in seen_serials:
                        new_serial = 1
                    seen_serials.add(serial)
            result.append({
                "user_id": user_id, "date": day,
                "first_login_hour": float(first_hour),
                "login_hour_deviation": float(max(start - first_hour, 0, first_hour - end)),
                "off_hours_events": float(((group["_hour"] < start - 1) | (group["_hour"] > end + 1)).sum()),
                "failed_logins": float(failed),
                "failed_login_ratio": failed / max(1, failed + counts["login"]),
                "downloads": float(downloads),
                "download_ratio": downloads / max(1.0, mean),
                "download_zscore": (downloads - mean) / max(std, 1.0),
                "mb_downloaded": sum(_size(value) for value in group.loc[group["activity"] == "file_download", "_metadata"]) / 1024,
                "uploads": float(counts["file_upload"]), "deletes": float(counts["file_delete"]),
                "renames": float(counts["file_rename"]), "usb_events": float(counts["usb_connect"]),
                "new_usb_serial": float(new_serial), "new_device": float(bool(devices - seen_devices)),
                "distinct_devices": float(len(devices)), "new_location": float(bool(locations - seen_locations)),
                "distinct_ips": float(len(ips)),
            })
            seen_devices.update(devices)
            seen_locations.update(locations)
            previous_downloads.append(downloads)
    return pd.DataFrame(result, columns=OUTPUT_COLUMNS)


def _date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def build_features(db, start=None, end=None, user_ids=None):
    """Recompute selected local dates using complete earlier history, then upsert.

    Date bounds are inclusive; an empty user_ids iterable selects no users.
    The caller's transaction is committed after successful persistence.
    """
    start, end = _date(start), _date(end)
    if start and end and start > end:
        raise ValueError("start must be on or before end")
    if user_ids is not None:
        user_ids = list(user_ids)
        if not user_ids:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)
    user_query = select(User.user_id, User.normal_login_start, User.normal_login_end,
                        User.normal_download_count, User.primary_device, User.home_location)
    event_query = select(Event.user_id, Event.timestamp, Event.activity, Event.device,
                         Event.ip, Event.location, Event.event_metadata)
    if user_ids is not None:
        user_query = user_query.where(User.user_id.in_(user_ids))
        event_query = event_query.where(Event.user_id.in_(user_ids))
    users = pd.DataFrame(db.execute(user_query).all(), columns=["user_id", "normal_login_start",
                         "normal_login_end", "normal_download_count", "primary_device", "home_location"])
    events = pd.DataFrame(db.execute(event_query).all(), columns=["user_id", "timestamp", "activity",
                          "device", "ip", "location", "metadata"])
    result = compute_features(events, users)
    if start:
        result = result[result["date"] >= start]
    if end:
        result = result[result["date"] <= end]
    records = result.to_dict("records")
    if not records:
        return result.reset_index(drop=True)
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        for index in range(0, len(records), 500):
            stmt = pg_insert(Feature.__table__).values(records[index:index + 500])
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "date"],
                set_={name: getattr(stmt.excluded, name) for name in FEATURE_COLUMNS},
            )
            db.execute(stmt)
    elif dialect == "sqlite":
        for index in range(0, len(records), 400):
            batch = records[index:index + 400]
            keys = [(row["user_id"], row["date"]) for row in batch]
            db.execute(delete(Feature).where(tuple_(Feature.user_id, Feature.date).in_(keys)))
            db.execute(Feature.__table__.insert(), batch)
    else:
        raise ValueError(f"Unsupported database: {dialect}")
    db.commit()
    return result.reset_index(drop=True)
