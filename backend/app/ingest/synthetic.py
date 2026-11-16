"""Generate reproducible synthetic CSVs without connecting to a database."""

import csv
import json
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=5, minutes=30))
DEFAULT_ANCHOR = date(2026, 11, 2)

# The profiles mirror the original SQL seed.
_PROFILES = [
    ("Priya Sharma", "Finance", "Accountant", 9, 18, 8, "Bengaluru", "WS-FIN-001"),
    ("Rahul Verma", "Engineering", "Backend Engineer", 10, 19, 15, "Bengaluru", "WS-ENG-002"),
    ("Ananya Iyer", "HR", "HR Manager", 9, 17, 6, "Mumbai", "WS-HR-003"),
    ("Vikram Rao", "Sales", "Account Executive", 9, 18, 12, "Delhi", "WS-SAL-004"),
    ("Sneha Kapoor", "Engineering", "Frontend Engineer", 10, 19, 14, "Bengaluru", "WS-ENG-005"),
    ("Arjun Mehta", "IT", "Sysadmin", 8, 17, 20, "Bengaluru", "WS-IT-006"),
    ("Kavya Nair", "Finance", "Finance Analyst", 9, 18, 10, "Bengaluru", "WS-FIN-007"),
    ("Rohan Gupta", "Marketing", "Content Lead", 10, 18, 9, "Mumbai", "WS-MKT-008"),
    ("Meera Joshi", "Legal", "Counsel", 9, 18, 7, "Delhi", "WS-LEG-009"),
    ("Aditya Singh", "Engineering", "DevOps Engineer", 9, 19, 18, "Hyderabad", "WS-ENG-010"),
    ("Ishita Das", "Sales", "Sales Manager", 9, 18, 11, "Kolkata", "WS-SAL-011"),
    ("Karan Malhotra", "IT", "Security Engineer", 9, 18, 16, "Bengaluru", "WS-IT-012"),
    ("Neha Reddy", "HR", "Recruiter", 9, 17, 5, "Hyderabad", "WS-HR-013"),
    ("Siddharth Jain", "Finance", "Controller", 9, 18, 9, "Mumbai", "WS-FIN-014"),
    ("Pooja Pillai", "Marketing", "Designer", 10, 19, 13, "Bengaluru", "WS-MKT-015"),
    ("Manish Kumar", "Engineering", "Data Engineer", 10, 19, 22, "Pune", "WS-ENG-016"),
    ("Divya Menon", "Legal", "Paralegal", 9, 17, 6, "Chennai", "WS-LEG-017"),
    ("Harsh Agarwal", "Engineering", "Tech Lead", 10, 19, 17, "Bengaluru", "WS-ENG-018"),
    ("Riya Bose", "Sales", "SDR", 9, 18, 8, "Kolkata", "WS-SAL-019"),
    ("Nikhil Patil", "IT", "Helpdesk", 8, 17, 10, "Pune", "WS-IT-020"),
]

USER_COLUMNS = ("user_id", "full_name", "department", "role", "normal_login_start",
                "normal_login_end", "normal_download_count", "home_location", "primary_device", "created_at")
EVENT_COLUMNS = ("event_id", "user_id", "timestamp", "activity_type", "activity",
                 "device", "ip", "location", "metadata", "source_key")


def generate_synthetic(out: str | Path, seed: int = 42,
                       anchor_date: date = DEFAULT_ANCHOR, days: int = 45) -> dict:
    """Write CSVs; return scenario event rows keyed S1 through S4.

    days is the number of preceding calendar days examined for weekday baseline.
    Timestamps are in fixed Asia/Kolkata offset.
    """
    if days < 0:
        raise ValueError("days must be nonnegative")
    rng = random.Random(seed)
    users = []
    created = datetime.combine(anchor_date - timedelta(days=days), time(), TZ).isoformat()
    for i, profile in enumerate(_PROFILES, 1):
        users.append(dict(zip(USER_COLUMNS, (f"EMP{i:03d}", *profile, created))))
    by_id = {u["user_id"]: u for u in users}
    events = []
    scenarios = {key: [] for key in ("S1", "S2", "S3", "S4")}

    def add(user, day, hour, minute, activity, metadata=None, *, second=0, device=None,
            ip=None, location=None, scenario=None):
        number = int(user["user_id"][3:])
        typ = ("login" if activity in ("login", "login_failed", "logout")
               else "file" if activity.startswith("file_")
               else "usb" if activity.startswith("usb_") else "device")
        row = {"user_id": user["user_id"],
               "timestamp": datetime.combine(day, time(hour, minute, second), TZ).isoformat(),
               "activity_type": typ, "activity": activity,
               "device": device or user["primary_device"],
               "ip": ip or f"10.0.{number}.{10 + number}",
               "location": location or user["home_location"],
               "metadata": metadata or {}, "source_key": ""}
        events.append(row)
        if scenario:
            scenarios[scenario].append(row)
        return row

    def baseline(user, day):
        start, end = user["normal_login_start"], user["normal_login_end"]
        add(user, day, start, rng.randrange(50), "login", {"success": True})
        if rng.random() < .15:
            add(user, day, start, rng.randrange(20), "login_failed", {"success": False})
        count = max(1, user["normal_download_count"] + int((rng.random() - .5) * user["normal_download_count"] * .6 // 1))
        for _ in range(count):
            add(user, day, rng.randrange(start + 1, end - 1), rng.randrange(59),
                "file_download", {"file": f"doc_{rng.randrange(100, 1000)}.pdf", "size_kb": rng.randrange(20, 4020)})
        for _ in range(rng.randint(1, 3)):
            add(user, day, start + 2 + rng.randrange(5), rng.randrange(59),
                "file_upload", {"file": f"report_{rng.randrange(10, 100)}.xlsx"})
        add(user, day, end, rng.randrange(50), "logout")
        if user["department"] == "IT" and rng.random() < .25:
            add(user, day, start + 3, 0, "usb_connect", {"serial": "KINGSTON-IT-STD"})

    for offset in range(days, 0, -1):
        day = anchor_date - timedelta(days=offset)
        if day.weekday() < 5:
            for user in users:
                baseline(user, day)

    # Anchor-day normal records for other employees, including the control.
    for user in users:
        if user["user_id"] in ("EMP007", "EMP013", "EMP018"):
            continue
        scenario = "S4" if user["user_id"] == "EMP004" else None
        if anchor_date.weekday() >= 5 and scenario is None:
            continue
        start = user["normal_login_start"]
        add(user, anchor_date, start, rng.randrange(50), "login", {"success": True}, scenario=scenario)
        count = user["normal_download_count"] * (4 if scenario else 1)
        for _ in range(count):
            add(user, anchor_date, start + 1 + rng.randrange(4), rng.randrange(59),
                "file_download", {"file": f"doc_{rng.randrange(100, 1000)}.pdf",
                                  "size_kb": rng.randrange(20, 4020)}, scenario=scenario)

    u = by_id["EMP007"]
    extra = {"device": "LAPTOP-UNKNOWN-77", "scenario": "S1"}
    add(u, anchor_date, 2, 7, "login", {"success": True}, **extra)
    for i in range(160):
        instant = datetime.combine(anchor_date, time(2, 15), TZ) + timedelta(seconds=i * 20)
        add(u, anchor_date, instant.hour, instant.minute, "file_download",
            {"file": f"finance/payroll_q{i % 4 + 1}_{i + 1}.xlsx", "size_kb": 901 + i},
            second=instant.second, **extra)
    add(u, anchor_date, 3, 20, "usb_connect", {"serial": "SANDISK-ULTRA-9F3A"}, **extra)
    add(u, anchor_date, 3, 48, "usb_disconnect", {"serial": "SANDISK-ULTRA-9F3A"}, **extra)

    u = by_id["EMP013"]
    for i in range(1, 9):
        add(u, anchor_date, 23, i, "login_failed", {"success": False},
            ip=f"185.220.101.{30 + i}", location="Frankfurt", scenario="S2")
    extra = {"ip": "185.220.101.44", "location": "Frankfurt", "scenario": "S2"}
    add(u, anchor_date, 23, 12, "login", {"success": True}, **extra)
    for i in range(1, 13):
        add(u, anchor_date, 23, 20 + i, "file_download",
            {"file": f"hr/candidates_{i}.csv", "size_kb": 300}, **extra)

    u = by_id["EMP018"]
    add(u, anchor_date, 10, 5, "login", {"success": True}, scenario="S3")
    for i in range(1, 46):
        add(u, anchor_date, 11, i, "file_download",
            {"file": f"repo/source_{i}.zip", "size_kb": 25000}, scenario="S3")
    add(u, anchor_date, 12, 10, "usb_connect", {"serial": "WD-PASSPORT-2TB"}, scenario="S3")
    for i in range(1, 71):
        instant = datetime.combine(anchor_date, time(13), TZ) + timedelta(seconds=i * 30)
        add(u, anchor_date, instant.hour, instant.minute, "file_delete",
            {"file": f"shared/design_docs/spec_{i}.md"}, second=instant.second, scenario="S3")

    # Add a device snapshot at the earliest successful login of each ISO week.
    seen = set()
    for row in sorted(events, key=lambda event: event["timestamp"]):
        if row["activity"] != "login":
            continue
        stamp = datetime.fromisoformat(row["timestamp"])
        key = (row["user_id"], *stamp.date().isocalendar()[:2])
        if key in seen:
            continue
        seen.add(key)
        number = int(row["user_id"][3:])
        add(by_id[row["user_id"]], stamp.date(), stamp.hour, stamp.minute, "device_info",
            {"hostname": row["device"], "os": "Windows 11",
             "mac": f"02:00:00:00:00:{number:02x}", "browser": "Chrome"},
            second=stamp.second, device=row["device"], ip=row["ip"], location=row["location"])

    events.sort(key=lambda row: (row["timestamp"], row["user_id"], row["activity"]))
    for index, row in enumerate(events, 1):
        row["event_id"] = index

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, fields, rows in (("users.csv", USER_COLUMNS, users), ("events.csv", EVENT_COLUMNS, events)):
        with (out / name).open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for row in rows:
                record = dict(row)
                if name == "events.csv":
                    record["metadata"] = json.dumps(record["metadata"], sort_keys=True, separators=(",", ":"))
                writer.writerow(record)
    return scenarios
