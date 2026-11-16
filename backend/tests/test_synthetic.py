import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from app.ingest.synthetic import generate_synthetic


def test_repeatability_and_scenarios(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    anchor = date(2026, 11, 2)
    scenarios = generate_synthetic(first, seed=42, anchor_date=anchor, days=45)
    assert scenarios == generate_synthetic(second, seed=42, anchor_date=anchor, days=45)
    for name in ("users.csv", "events.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    counts = {key: Counter(row["activity"] for row in rows) for key, rows in scenarios.items()}
    assert counts["S1"] == {"login": 1, "file_download": 160, "usb_connect": 1, "usb_disconnect": 1}
    assert counts["S2"] == {"login_failed": 8, "login": 1, "file_download": 12}
    assert counts["S3"] == {"login": 1, "file_download": 45, "usb_connect": 1, "file_delete": 70}
    assert counts["S4"] == {"login": 1, "file_download": 48}
    assert scenarios["S1"][0]["timestamp"].endswith("02:07:00+05:30")
    assert scenarios["S1"][1]["timestamp"].endswith("02:15:00+05:30")
    assert all(row["location"] == "Frankfurt" for row in scenarios["S2"])
    with (first / "events.csv").open(newline="", encoding="utf-8") as file:
        events = list(csv.DictReader(file))
    assert all(datetime.fromisoformat(row["timestamp"]).date() <= anchor for row in events)
    assert all(datetime.fromisoformat(row["timestamp"]).date().weekday() < 5
               for row in events if datetime.fromisoformat(row["timestamp"]).date() < anchor)
    logins = defaultdict(list)
    snapshots = defaultdict(list)
    for row in events:
        stamp = datetime.fromisoformat(row["timestamp"])
        key = (row["user_id"], *stamp.date().isocalendar()[:2])
        if row["activity"] == "login":
            logins[key].append(row)
        if row["activity"] == "device_info":
            snapshots[key].append(row)
    assert logins.keys() == snapshots.keys()
    for key in logins:
        assert len(snapshots[key]) == 1
        snapshot = snapshots[key][0]
        assert snapshot["timestamp"] == min(row["timestamp"] for row in logins[key])
        assert set(json.loads(snapshot["metadata"])) == {"hostname", "os", "mac", "browser"}

    for key, rows in scenarios.items():
        user_id = rows[0]["user_id"]
        actual = Counter(row["activity"] for row in events
                         if row["user_id"] == user_id
                         and datetime.fromisoformat(row["timestamp"]).date() == anchor
                         and row["activity"] != "device_info")
        assert actual == counts[key]
    usb = [row for row in scenarios["S1"] if row["activity"].startswith("usb_")]
    assert [row["timestamp"][11:16] for row in usb] == ["03:20", "03:48"]
    assert all(row["metadata"]["serial"] == "SANDISK-ULTRA-9F3A" for row in usb)
    assert all(row["metadata"]["size_kb"] == 25000 for row in scenarios["S3"]
               if row["activity"] == "file_download")


def test_weekend_anchor_has_only_scenario_activity(tmp_path):
    anchor = date(2026, 11, 1)
    generate_synthetic(tmp_path, anchor_date=anchor, days=2)
    with (tmp_path / "events.csv").open(newline="", encoding="utf-8") as file:
        events = list(csv.DictReader(file))
    anchor_users = {row["user_id"] for row in events
                    if datetime.fromisoformat(row["timestamp"]).date() == anchor}
    assert anchor_users == {"EMP004", "EMP007", "EMP013", "EMP018"}
