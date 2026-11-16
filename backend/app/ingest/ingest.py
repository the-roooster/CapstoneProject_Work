"""Streaming CSV and CERT ingestion.

Callers supply a SQLAlchemy Session. Batches are committed independently.
Naive timestamps, including CERT timestamps, are interpreted as UTC.
"""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.ingest.activities import ACTIVITY_TYPES
from app.models import Event, User

BATCH_SIZE = 5000


@dataclass
class IngestReport:
    rows_read: int = 0
    inserted: int = 0
    skipped_by_reason: dict[str, int] = field(default_factory=dict)

    def skip(self, reason, count=1):
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + count


def _rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        reader.fieldnames = [name.strip().lower() for name in reader.fieldnames]
        for row in reader:
            yield {key: (value.strip() if isinstance(value, str) else value)
                   for key, value in row.items() if key is not None}


def _timestamp(value, cert=False):
    try:
        if cert:
            parsed = datetime.strptime(value, "%m/%d/%Y %H:%M:%S")
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _insert_batch(session, model, rows, report, conflict_column):
    if not rows:
        return
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        insert = sqlite_insert
    elif dialect == "postgresql":
        insert = pg_insert
    else:
        raise ValueError(f"Unsupported database: {dialect}")
    stmt = insert(model.__table__).on_conflict_do_nothing(index_elements=[conflict_column])
    result = session.execute(stmt, rows)
    inserted = result.rowcount
    session.commit()
    report.inserted += inserted
    if inserted != len(rows):
        report.skip("duplicate", len(rows) - inserted)
    rows.clear()


def load_users_csv(session, path):
    report, batch = IngestReport(), []
    required = ("user_id", "full_name", "department", "role", "home_location", "primary_device")
    for row in _rows(path):
        report.rows_read += 1
        if any(not row.get(name) for name in required):
            report.skip("missing_required")
            continue
        try:
            values = {name: row[name] for name in required}
            for name, default in (("normal_login_start", 9), ("normal_login_end", 18),
                                  ("normal_download_count", 10)):
                values[name] = int(row.get(name) or default)
            if row.get("created_at"):
                values["created_at"] = _timestamp(row["created_at"])
                if values["created_at"] is None:
                    report.skip("invalid_timestamp")
                    continue
        except (ValueError, TypeError):
            report.skip("invalid_number")
            continue
        # Keep all rows in a batch structurally identical for bulk insertion.
        values.setdefault("created_at", datetime(1970, 1, 1, tzinfo=timezone.utc))
        batch.append(values)
        if len(batch) >= BATCH_SIZE:
            _insert_batch(session, User, batch, report, "user_id")
    _insert_batch(session, User, batch, report, "user_id")
    return report


def _event(row):
    required = ("user_id", "timestamp", "activity", "device", "ip", "location")
    if any(not row.get(key) for key in required):
        return None, "missing_required"
    timestamp = _timestamp(row["timestamp"])
    if timestamp is None:
        return None, "invalid_timestamp"
    activity = row["activity"]
    if activity not in ACTIVITY_TYPES:
        return None, "unknown_activity"
    if row.get("activity_type") and row["activity_type"] != ACTIVITY_TYPES[activity]:
        return None, "activity_type_mismatch"
    try:
        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict):
            raise ValueError()
        serialized = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError):
        return None, "invalid_metadata"
    key = "|".join((row["user_id"], timestamp.isoformat(), activity, row["device"], serialized))
    return {"user_id": row["user_id"], "timestamp": timestamp,
            "activity_type": ACTIVITY_TYPES[activity], "activity": activity,
            "device": row["device"], "ip": row["ip"], "location": row["location"],
            "metadata": metadata, "source_key": hashlib.sha1(key.encode("utf-8")).hexdigest()}, None


def _consume_events(session, rows, report):
    batch = []
    # Bounded lookup cache: query only the IDs in the current input batch.
    pending = []

    def flush():
        if not pending:
            return
        ids = {item["user_id"] for item in pending}
        known = set()
        ids = list(ids)
        for start in range(0, len(ids), 500):
            known.update(session.scalars(select(User.user_id).where(User.user_id.in_(ids[start:start + 500]))))
        for item in pending:
            if item["user_id"] not in known:
                report.skip("unknown_user")
            else:
                batch.append(item)
        pending.clear()
        _insert_batch(session, Event, batch, report, "source_key")

    for row, error in rows:
        report.rows_read += 1
        if error:
            report.skip(error)
        else:
            pending.append(row)
            if len(pending) >= BATCH_SIZE:
                flush()
    flush()
    return report


def load_events_csv(session, path):
    return _consume_events(session, (_event(row) for row in _rows(path)), IngestReport())


def _cert_event(row, kind):
    user = (row.get("user") or "").split("/")[-1]
    stamp = _timestamp(row.get("date"), cert=True)
    raw = (row.get("activity") or "").lower()
    filename = row.get("filename") or ""
    if not user or not row.get("date"):
        return None, "missing_required"
    if stamp is None:
        return None, "invalid_timestamp"
    if kind == "logon":
        activity = {"logon": "login", "logoff": "logout"}.get(raw)
    elif kind == "device":
        activity = {"connect": "usb_connect", "disconnect": "usb_disconnect"}.get(raw)
    else:
        activity = "file_delete" if "delete" in raw else "file_download" if filename or raw else None
    if activity is None:
        return None, "unknown_activity"
    metadata = {"source": f"cert:{kind}"}
    if filename:
        metadata["filename"] = filename
    return _event({"user_id": user, "timestamp": stamp.isoformat(), "activity": activity,
                   "device": row.get("pc") or "unknown", "ip": "0.0.0.0",
                   "location": "Unknown", "metadata": metadata})


def _kind(path):
    name = Path(path).stem.lower()
    if name in ("logon", "device", "file"):
        return name
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        header = [h.strip().lower() for h in (reader.fieldnames or [])]
        if "filename" in header:
            return "file"
        for row in reader:
            normalized = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
            activity = (normalized.get("activity") or "").strip().lower()
            if activity in ("logon", "logoff"):
                return "logon"
            if activity in ("connect", "disconnect"):
                return "device"
    raise ValueError(f"Unrecognised CERT file: {path}")


def _cert_rows(paths, limit):
    consumed = 0
    for path in paths:
        kind = _kind(path)
        for row in _rows(path):
            if limit is not None and consumed >= limit:
                return
            consumed += 1
            yield _cert_event(row, kind)


def _percentile(histogram, fraction, default):
    count = sum(histogram.values())
    if not count:
        return default
    position = (count - 1) * fraction
    low, high = math.floor(position), math.ceil(position)
    values = []
    seen = 0
    for hour, number in sorted(histogram.items()):
        if seen <= low < seen + number:
            a = hour
        if seen <= high < seen + number:
            b = hour
            break
        seen += number
    return round(a + (b - a) * (position - low))


def load_cert(session, paths, limit=None):
    """Import CERT files, creating missing users from their earliest 14 calendar days.

    Paths may be an iterable, a file, or a directory. limit applies across files.
    Three streaming passes find first dates, collect baselines, then insert.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative")
    if isinstance(paths, (str, Path)):
        path = Path(paths)
        paths = sorted(path.glob("*.csv")) if path.is_dir() else [path]
    else:
        paths = sorted(map(Path, paths))
    first = {}
    for event, error in _cert_rows(paths, limit):
        if error:
            continue
        user, day = event["user_id"], event["timestamp"].date()
        first[user] = min(first.get(user, day), day)
    existing = set()
    ids = list(first)
    for start in range(0, len(ids), 500):
        existing.update(session.scalars(select(User.user_id).where(User.user_id.in_(ids[start:start + 500]))))
    unknown = set(first) - existing
    hours, devices, downloads = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for event, error in _cert_rows(paths, limit):
        if error or event["user_id"] not in unknown:
            continue
        user, stamp = event["user_id"], event["timestamp"]
        if not first[user] <= stamp.date() < first[user] + timedelta(days=14):
            continue
        devices[user][event["device"]] += 1
        if event["activity"] == "login":
            hours[user][stamp.hour] += 1
        if event["activity"] == "file_download":
            downloads[user][stamp.date()] += 1
    users = []
    dummy = IngestReport()
    for user in sorted(unknown):
        counts = [downloads[user][first[user] + timedelta(days=i)] for i in range(14)]
        device = min(devices[user], key=lambda value: (-devices[user][value], value)) if devices[user] else "unknown"
        users.append({"user_id": user, "full_name": user, "department": "Unknown", "role": "Unknown",
                      "normal_login_start": _percentile(hours[user], .1, 9),
                      "normal_login_end": _percentile(hours[user], .9, 18),
                      "normal_download_count": int(median(counts)), "home_location": "Unknown",
                      "primary_device": device, "created_at": datetime.combine(first[user], datetime.min.time(), timezone.utc)})
        if len(users) >= BATCH_SIZE:
            _insert_batch(session, User, users, dummy, "user_id")
    _insert_batch(session, User, users, dummy, "user_id")
    return _consume_events(session, _cert_rows(paths, limit), IngestReport())
