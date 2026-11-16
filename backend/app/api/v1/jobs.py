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


def _new_job():
    job_id = str(uuid.uuid4())
    with _LOCK:
        JOBS[job_id] = {"status": "running", "report": None}
    return job_id


def _finish(job_id, status, report):
    with _LOCK:
        JOBS[job_id] = {"status": status, "report": report}


def _ingest_job(job_id, directory, cleanup):
    try:
        from app.ingest.ingest import load_events_csv, load_users_csv
        with SessionLocal() as db:
            users = load_users_csv(db, Path(directory) / "users.csv")
            events = load_events_csv(db, Path(directory) / "events.csv")
        _finish(job_id, "done", {"users": asdict(users), "events": asdict(events)})
    except Exception as exc:
        _finish(job_id, "error", {"error": str(exc)})
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
    except Exception as exc:
        _finish(job_id, "error", {"error": str(exc)})


@router.post("/ingest/run", response_model=JobCreated)
def run_ingest(background: BackgroundTasks, source: str | None = Query(None),
               files: list[UploadFile] | None = File(None)):
    if source == "synthetic":
        if files:
            raise HTTPException(422, "Choose synthetic source or files, not both")
        # Relative to the repository root, independent of the server's working directory.
        directory = Path(__file__).resolve().parents[4] / "data" / "synthetic"
        if not all((directory / name).is_file() for name in ("users.csv", "events.csv")):
            raise HTTPException(404, "Synthetic CSV files not found")
        cleanup = False
    elif source is None:
        if not files or sorted(file.filename for file in files) != ["events.csv", "users.csv"]:
            raise HTTPException(422, "Upload users.csv and events.csv")
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
    background.add_task(_ingest_job, job_id, str(directory), cleanup)
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
