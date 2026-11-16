from io import BytesIO
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import jobs
from app.models import Base, Event, SCHEMA, User


def test_cert_upload_job_ingests_and_cleans_up(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           execution_options={"schema_translate_map": {SCHEMA: None}})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(jobs, "SessionLocal", factory)
    body = b"id,date,user,pc,activity\n1,01/02/2010 06:49:00,ALICE,PC1,Logon\n"
    upload = UploadFile(filename="logon.csv", file=BytesIO(body))
    tasks = BackgroundTasks()
    result = jobs.run_ingest(tasks, source=None, files=[upload])
    task = tasks.tasks[0]
    temp_dir = Path(task.args[1])
    try:
        task.func(*task.args, **task.kwargs)
        report = jobs.JOBS[result["job_id"]]
        assert report["status"] == "done"
        assert report["report"]["events"]["rows_read"] == 1
        assert report["report"]["events"]["inserted"] == 1
        assert not temp_dir.exists()
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(User)) == 1
            assert db.scalar(select(func.count()).select_from(Event)) == 1
    finally:
        engine.dispose()


def test_reject_unknown_file_name():
    upload = UploadFile(filename="../unsafe.csv", file=BytesIO(b""))
    with pytest.raises(HTTPException) as error:
        jobs.run_ingest(BackgroundTasks(), source=None, files=[upload])
    assert error.value.status_code == 422
