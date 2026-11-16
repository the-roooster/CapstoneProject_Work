import csv
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.ingest.ingest import load_cert, load_events_csv, load_users_csv
from app.ingest.synthetic import generate_synthetic
from app.models import Base, Event, SCHEMA, User


def db():
    engine = create_engine("sqlite:///:memory:", execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    return Session(engine)


def test_synthetic_and_bad_rows(tmp_path):
    generate_synthetic(tmp_path, days=2)
    with db() as session:
        users = load_users_csv(session, tmp_path / "users.csv")
        events = load_events_csv(session, tmp_path / "events.csv")
        assert users.inserted == 20
        assert events.inserted > 0
        assert events.rows_read == events.inserted + events.skipped_by_reason.get("duplicate", 0)
        assert load_users_csv(session, tmp_path / "users.csv").inserted == 0
        assert load_events_csv(session, tmp_path / "events.csv").inserted == 0

        path = tmp_path / "bad.csv"
        path.write_text(
            "user_id,timestamp,activity,device,ip,location,metadata\n"
            "EMP001,bad,login,PC,1,x,{}\n"
            "NOBODY,2026-01-01T00:00:00Z,login,PC,1,x,{}\n"
            "EMP001,2026-01-01T00:00:00Z,unknown,PC,1,x,{}\n"
            "EMP001,2026-01-01T00:00:00Z,login,,1,x,{}\n",
            encoding="utf-8",
        )
        bad = load_events_csv(session, path)
        assert bad.rows_read == 4
        assert bad.inserted == 0
        assert bad.skipped_by_reason == {"invalid_timestamp": 1, "unknown_user": 1,
                                         "unknown_activity": 1, "missing_required": 1}


def test_cert_baselines_and_idempotence(tmp_path):
    (tmp_path / "logon.csv").write_text(
        "id,date,user,pc,activity\n"
        "1,01/02/2010 06:49:00,domain/ALICE,PC1,Logon\n"
        "2,01/02/2010 17:00:00,domain/ALICE,PC1,Logoff\n"
        "3,01/03/2010 10:00:00,domain/ALICE,PC2,Logon\n"
        "4,not-a-date,domain/ALICE,PC1,Logon\n",
        encoding="utf-8",
    )
    (tmp_path / "file.csv").write_text(
        'id,date,user,pc,activity,filename\n'
        '5,01/02/2010 08:00:00,domain/ALICE,PC1,Open,"file, one.txt"\n'
        '6,01/02/2010 08:01:00,domain/ALICE,PC1,Delete,file.txt\n',
        encoding="utf-8",
    )
    with db() as session:
        report = load_cert(session, tmp_path)
        assert (report.rows_read, report.inserted, report.skipped_by_reason) == (6, 5, {"invalid_timestamp": 1})
        user = session.get(User, "ALICE")
        assert (user.normal_login_start, user.normal_login_end, user.primary_device) == (6, 10, "PC1")
        assert user.home_location == "Unknown"
        assert user.normal_download_count == 0
        assert session.scalar(select(func.count()).select_from(Event)) == 5
        activities = set(session.scalars(select(Event.activity)))
        assert activities == {"login", "logout", "file_download", "file_delete"}
        repeat = load_cert(session, tmp_path)
        assert repeat.inserted == 0
        assert repeat.skipped_by_reason == {"invalid_timestamp": 1, "duplicate": 5}


def test_more_than_one_batch(tmp_path):
    path = tmp_path / "events.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["user_id", "timestamp", "activity", "device", "ip", "location", "metadata"])
        for i in range(50001):
            writer.writerow(["A", "2026-01-01T00:00:00Z", "file_download",
                             "PC", "1", "X", '{"file":"' + str(i) + '"}'])
    with db() as session:
        session.add(User(user_id="A", full_name="A", department="IT", role="R",
                         home_location="X", primary_device="PC"))
        session.commit()
        report = load_events_csv(session, path)
        assert (report.rows_read, report.inserted) == (50001, 50001)
        assert load_events_csv(session, path).inserted == 0
