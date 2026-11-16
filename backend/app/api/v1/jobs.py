import logging
import shutil
import tempfile
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from app.db import SessionLocal
from app.schemas import JobCreated, JobOut

router = APIRouter(tags=["jobs"])
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_LOG = logging.getLogger(__name__)


def _new_job():
    job_id = str(uuid.uuid4())
    with _LOCK:
        JOBS[job_id] = {"status": "running", "report": None}
    return job_id


def _finish(job_id, status, report):
    with _LOCK:
        JOBS[job_id] = {"status": status, "report": report}


def _ingest_job(job_id, directory, cleanup, mode="synthetic"):
    try:
        from app.ingest.ingest import load_cert, load_events_csv, load_users_csv
        with SessionLocal() as db:
            if mode == "cert":
                report = {"events": asdict(load_cert(db, Path(directory)))}
            else:
                users = load_users_csv(db, Path(directory) / "users.csv")
                events = load_events_csv(db, Path(directory) / "events.csv")
                report = {"users": asdict(users), "events": asdict(events)}
        _finish(job_id, "done", report)
    except Exception:
        _LOG.exception("Ingestion job failed")
        _finish(job_id, "error", {"error": "Ingestion failed"})
    finally:
        if cleanup:
            shutil.rmtree(directory, ignore_errors=True)


def _score_job(job_id, retrain):
    try:
        from app.features.build_features import build_features
        from app.ml.registry import load_latest
        from app.ml.scoring import score_features
        from app.ml.train import train
        from app.explain.run import explain_all
        with SessionLocal() as db:
            features = build_features(db)
            try:
                artifact = load_latest()
            except FileNotFoundError:
                artifact = None
            version = train(db) if retrain or artifact is None else artifact["version"]
            scored = score_features(db)
            explained = explain_all(db)
        _finish(job_id, "done", {"features": len(features), "model_version": version,
                                  "scored": scored, "explained": explained})
    except Exception:
        _LOG.exception("Scoring job failed")
        _finish(job_id, "error", {"error": "Scoring failed"})


@router.post("/ingest/run", response_model=JobCreated)
def run_ingest(background: BackgroundTasks, source: str | None = Query(None),
               files: list[UploadFile] | None = File(None)):
    mode = "synthetic"
    if source == "synthetic":
        if files:
            raise HTTPException(422, "Choose synthetic source or files, not both")
        # Relative to the repository root, independent of the server's working directory.
        directory = Path(__file__).resolve().parents[4] / "data" / "synthetic"
        if not all((directory / name).is_file() for name in ("users.csv", "events.csv")):
            raise HTTPException(404, "Synthetic CSV files not found")
        cleanup = False
    elif source is None:
        names = [file.filename for file in (files or [])]
        cert_names = {"logon.csv", "device.csv", "file.csv"}
        if not names or len(names) != len(set(names)):
            raise HTTPException(422, "Upload distinct CERT CSV files or users.csv and events.csv")
        if set(names) == {"events.csv", "users.csv"}:
            mode = "synthetic"
        elif set(names) <= cert_names:
            mode = "cert"
        else:
            raise HTTPException(422, "Upload logon.csv, device.csv and/or file.csv")
        directory = Path(tempfile.mkdtemp(prefix="sentinel-ingest-"))
        try:
            for file in files:
                with (directory / file.filename).open("wb") as target:
                    shutil.copyfileobj(file.file, target)
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        cleanup = True
    else:
        raise HTTPException(422, "Unknown ingest source")
    job_id = _new_job()
    background.add_task(_ingest_job, job_id, str(directory), cleanup, mode)
    return {"job_id": job_id}


@router.post("/score/run", response_model=JobCreated)
def run_score(background: BackgroundTasks, retrain: bool = False):
    job_id = _new_job()
    background.add_task(_score_job, job_id, retrain)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}", response_model=JobOut)
def job(job_id: str):
    with _LOCK:
        item = JOBS.get(job_id)
    if item is None:
        raise HTTPException(404, "Job not found")
    return item
