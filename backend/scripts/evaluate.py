"""Evaluate CERT or synthetic data in an isolated in-memory SQLite database.

From backend/: python -m scripts.evaluate [--cert-dir PATH] [--answers PATH] [--model iforest|lof]
No production tables or saved models are changed. Answer CSVs must identify a
user and either a start/end interval or dated insider events.
"""
import argparse
import csv
import json
import math
import os
import random
import tempfile
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Evaluation uses its own in-memory engine, not DATABASE_URL or the model registry.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "evaluation-only-secret-not-used-for-authentication")

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.explain.rules import explain
from app.features.build_features import build_features
from app.features.columns import FEATURE_COLUMNS
from app.ingest.ingest import load_cert, load_events_csv, load_users_csv
from app.ingest.synthetic import generate_synthetic
from app.ml.calibration import Calibration
from app.ml.iforest import IsolationForestModel
from app.ml.lof import LocalOutlierFactorModel
from app.models import Base, Event, Feature, SCHEMA, User

SEED = 42
ANCHOR = date(2026, 11, 2)
DAYS = 45
USER_FIELDS = ("user", "user_id", "employee_id", "employee", "userid")
START_FIELDS = ("start", "start_date", "begin", "begin_date", "from")
END_FIELDS = ("end", "end_date", "finish", "finish_date", "to")
DATE_FIELDS = ("date", "timestamp", "datetime", "time")


def _csv_rows(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"Missing CSV header: {path}")
        reader.fieldnames = [header.strip().lower() for header in reader.fieldnames]
        for row in reader:
            yield {key: (value.strip() if isinstance(value, str) else value)
                   for key, value in row.items() if key is not None}


def _first(row, fields):
    return next((row.get(field) for field in fields if row.get(field)), None)


def _date(value):
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def discover_answers(cert_dir, explicit=None):
    if explicit is not None:
        source = Path(explicit)
        if not source.exists():
            raise ValueError(f"Answer path does not exist: {source}")
        return sorted(source.rglob("*.csv")) if source.is_dir() else [source]
    return sorted(path for path in Path(cert_dir).rglob("*.csv")
                  if any("answer" in part.lower() or "insider" in part.lower()
                         for part in path.relative_to(cert_dir).parts))


def read_answers(paths):
    """Return user -> inclusive date intervals, accepting interval or event rows."""
    intervals = defaultdict(list)
    event_dates = defaultdict(list)
    invalid = 0
    for path in paths:
        for row in _csv_rows(path):
            user = (_first(row, USER_FIELDS) or "").split("/")[-1].strip()
            start_value, end_value = _first(row, START_FIELDS), _first(row, END_FIELDS)
            if start_value or end_value:
                start, end = _date(start_value), _date(end_value)
                if not user or not start or not end or end < start:
                    invalid += 1
                    continue
                intervals[user].append((start, end))
            else:
                day = _date(_first(row, DATE_FIELDS))
                if not user or not day:
                    invalid += 1
                    continue
                # Dated incident records in each file form one inclusive interval.
                event_dates[(str(path), user)].append(day)
    for (_, user), days in event_dates.items():
        intervals[user].append((min(days), max(days)))
    if not intervals:
        raise ValueError("No usable insider labels: provide CSVs with user and start/end dates, or dated insider events")
    return dict(intervals), invalid


def discover_events(cert_dir):
    allowed = {"logon", "device", "file"}
    return sorted(path for path in Path(cert_dir).rglob("*.csv")
                  if path.stem.lower() in allowed and not any(
                      "answer" in part.lower() or "insider" in part.lower()
                      for part in path.relative_to(cert_dir).parts))


def filtered_cert(paths, insiders, directory):
    """Stream a reproducible insider + up-to-200-other-user sample to temp CSVs."""
    users = set()
    for path in paths:
        for row in _csv_rows(path):
            user = (row.get("user") or "").split("/")[-1].strip()
            if user:
                users.add(user)
    other = sorted(users - set(insiders))
    selected = set(insiders) | set(random.Random(SEED).sample(other, min(200, len(other))))
    output = []
    for number, path in enumerate(paths):
        dest = Path(directory) / str(number) / path.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with path.open("r", encoding="utf-8-sig", newline="") as source, dest.open("w", encoding="utf-8", newline="") as target:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise ValueError(f"Missing CSV header: {path}")
            reader.fieldnames = [field.strip().lower() for field in reader.fieldnames]
            writer = csv.DictWriter(target, fieldnames=reader.fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                user = (row.get("user") or "").strip().split("/")[-1]
                if user in selected:
                    writer.writerow(row)
        output.append(dest)
    return output, len(users), len(selected & users)


def label(user, day, answers):
    return any(start <= day <= end for start, end in answers.get(user, ()))


def ranking_metrics(frame, column):
    ordered = frame.sort_values([column, "date", "user_id"],
                                ascending=[False, True, True], kind="stable").reset_index(drop=True)
    positives = int(ordered["positive"].sum())
    top5 = max(1, math.ceil(len(ordered) * .05))
    result = {}
    for requested in (10, 50):
        top = ordered.head(requested)
        result[f"p{requested}"] = float(top["positive"].mean()) if len(top) else 0.0
        result[f"users{requested}"] = int(top.loc[top["positive"], "user_id"].nunique())
    result["recall5"] = float(ordered.head(top5)["positive"].sum() / positives) if positives else None
    result["top5"] = top5
    return result


def _format_recall(value):
    return f"{value:.3f}" if value is not None else "N/A (no labelled positive test user-days)"


def evaluate(cert_dir=None, answer_path=None, model_name="iforest"):
    if model_name not in ("iforest", "lof"):
        raise ValueError(f"Unknown model: {model_name}")
    output = []
    emit = output.append
    with tempfile.TemporaryDirectory(prefix="sentinel-evaluation-") as scratch:
        tmp = Path(scratch)
        cert = Path(cert_dir) if cert_dir is not None else None
        event_paths = discover_events(cert) if cert and cert.is_dir() else []
        if cert is not None and cert.exists() and not cert.is_dir():
            raise ValueError(f"CERT path is not a directory: {cert}")
        if event_paths:
            label_paths = discover_answers(cert, answer_path)
            if not label_paths:
                raise ValueError("CERT event CSVs found but no answers; provide --answers")
            answers, invalid_answers = read_answers(label_paths)
            selected_paths, population, selected = filtered_cert(event_paths, answers, tmp)
            mode = "CERT"
            scenarios = None
        else:
            emit("synthetic only")
            if answer_path is not None:
                emit("CERT event files were not found; the supplied answers were not used.")
            scenarios = generate_synthetic(tmp / "synthetic", seed=SEED, anchor_date=ANCHOR, days=DAYS)
            answers = defaultdict(list)
            tz = ZoneInfo(settings.APP_TZ)
            for key in ("S1", "S2", "S3"):
                for event in scenarios[key]:
                    local_date = datetime.fromisoformat(event["timestamp"]).astimezone(tz).date()
                    answers[event["user_id"]].append((local_date, local_date))
            answers = dict(answers)
            invalid_answers = 0
            mode, population, selected = "synthetic", 20, 20

        engine = create_engine("sqlite://", poolclass=StaticPool,
                               execution_options={"schema_translate_map": {SCHEMA: None}})
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                if mode == "CERT":
                    report = load_cert(db, selected_paths)
                    ingest = f"events read={report.rows_read}, inserted={report.inserted}, skipped={sum(report.skipped_by_reason.values())}"
                else:
                    user_report = load_users_csv(db, tmp / "synthetic" / "users.csv")
                    report = load_events_csv(db, tmp / "synthetic" / "events.csv")
                    ingest = f"users inserted={user_report.inserted}; events read={report.rows_read}, inserted={report.inserted}, skipped={sum(report.skipped_by_reason.values())}"
                build_features(db)
                feature_rows = list(db.scalars(select(Feature).order_by(Feature.user_id, Feature.date)))
                user_rows = {u.user_id: u for u in db.scalars(select(User))}
                event_rows = defaultdict(list)
                for event in db.scalars(select(Event).order_by(Event.user_id, Event.timestamp, Event.event_id)):
                    event_rows[event.user_id].append(event)
                if not feature_rows:
                    raise ValueError("No valid feature user-days were produced")
                dates = sorted({f.date for f in feature_rows})
                split = math.floor(len(dates) * .7)
                if split < 1 or split >= len(dates):
                    raise ValueError("At least two distinct active dates are required")
                cutoff = dates[split]
                train = [f for f in feature_rows if f.date < cutoff]
                test = [f for f in feature_rows if f.date >= cutoff]
                train_x = pd.DataFrame([{name: getattr(f, name) for name in FEATURE_COLUMNS} for f in train], columns=FEATURE_COLUMNS)
                test_x = pd.DataFrame([{name: getattr(f, name) for name in FEATURE_COLUMNS} for f in test], columns=FEATURE_COLUMNS)
                model = (IsolationForestModel() if model_name == "iforest" else LocalOutlierFactorModel()).fit(train_x)
                training_scores = model.score(train_x)
                scores = model.score(test_x)
                history = defaultdict(list)
                rule_scores = {}
                for f in feature_rows:
                    prev = history[f.user_id][-14:]
                    mean = sum(prev) / len(prev) if prev else user_rows[f.user_id].normal_download_count
                    if f.date >= cutoff:
                        reasons = explain(user_rows[f.user_id], f, {"download_mean": mean}, event_rows[f.user_id])
                        rule_scores[(f.user_id, f.date)] = sum(reason["severity"] for reason in reasons)
                    history[f.user_id].append(f.downloads)
                frame = pd.DataFrame([{"user_id": f.user_id, "date": f.date,
                                       "positive": label(f.user_id, f.date, answers),
                                       "model": float(score), "rules": rule_scores[(f.user_id, f.date)]}
                                      for f, score in zip(test, scores, strict=True)])
                frame["combined"] = (frame["model"].rank(method="average", pct=True)
                                     + frame["rules"].rank(method="average", pct=True)) / 2
                positives = int(frame["positive"].sum())
                positive_users = int(frame.loc[frame["positive"], "user_id"].nunique())
                grid = []
                for high in (99.9, 99.5, 99):
                    for medium in (99, 97, 95):
                        cal = Calibration.from_training_scores(training_scores, medium, high)
                        alerts = frame["model"] >= cal.med_cut
                        highs = frame["model"] >= cal.high_cut
                        grid.append((high, medium, float(alerts.mean() * 1000),
                                     float(highs.mean() * 1000),
                                     float((frame["positive"] & alerts).sum() / positives) if positives else None))
        finally:
            engine.dispose()

    emit(f"Dataset: {mode}; seed={SEED}; timezone={settings.APP_TZ}; sample={selected}/{population} users (all labelled insiders plus up to 200 others).")
    emit(f"Model: {model_name}.")
    if mode == "synthetic":
        emit(f"Synthetic: anchor={ANCHOR.isoformat()}, {DAYS} preceding calendar days; EMP007, EMP013 and EMP018 are positive scenarios; EMP004 is a negative control.")
    else:
        emit(f"Answer files: {len(label_paths)}; invalid answer rows skipped: {invalid_answers}.")
    emit(f"Ingest: {ingest}.")
    emit(f"Split: {len(dates)} distinct active dates; first {split} dates train ({len(train)} user-days), remaining {len(dates)-split} dates test ({len(test)} user-days), test starts {cutoff}.")
    emit(f"Test labels: {positives} positive user-days across {positive_users} insiders.")
    emit("Rankings: P@10 | P@50 | recall@top5% | insiders@10 | insiders@50")
    for column, label_name in (("model", "Model only"), ("rules", "Rules only"), ("combined", "Combined (evaluation only)")):
        metric = ranking_metrics(frame, column)
        emit(f"{label_name}: {metric['p10']:.3f} | {metric['p50']:.3f} | {_format_recall(metric['recall5'])} (top {metric['top5']}) | {metric['users10']} | {metric['users50']}")
    emit("Grid: HIGH_PCT | MEDIUM_PCT | medium+high alerts/1000 | high alerts/1000 | recall (medium+high)")
    for high, medium, alert_rate, high_rate, recall in grid:
        emit(f"{high:g} | {medium:g} | {alert_rate:.2f} | {high_rate:.2f} | {_format_recall(recall)}")
    eligible = [row for row in grid if row[4] is not None]
    if eligible:
        # Choose the lowest alert rate among the highest-recall settings; break ties
        # toward fewer high alerts, then the higher medium/high percentile.
        best = min(eligible, key=lambda row: (-row[4], row[2], row[3], -row[1], -row[0]))
        emit(f"Suggested evaluation defaults: HIGH_PCT={best[0]:g}, MEDIUM_PCT={best[1]:g} (highest measured recall, then lowest medium+high and high alert rates; not a product configuration change).")
        if mode == "synthetic":
            control = frame[(frame["user_id"] == "EMP004") & (frame["date"] == ANCHOR)]
            if not control.empty:
                control_cal = Calibration.from_training_scores(training_scores, best[1], best[0])
                control_score = float(control.iloc[0]["model"])
                emit(f"EMP004 negative control at suggested defaults: {control_cal.level(control_score)} (anomaly_score={control_score:.6f}).")
    else:
        emit("Suggested evaluation defaults: none; no positive test user-days to measure recall.")
    emit("Caveats: the time split is by distinct active dates, not a random user split; training may include labelled insiders. Evaluation labels are user-day intervals, not proof that every event in an interval is malicious.")
    emit("CERT caveat: CERT imports use placeholder IP and location values; NEW_LOCATION never fires for CERT-only users. Unknown-user baselines use their first 14 days and can cross the train/test boundary.")
    emit("Synthetic caveat: results describe seeded scenarios and do not establish performance on real insider threats. Combined ranking is comparison-only and is not the product score.")
    return "\n".join(output) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate user-day anomaly rankings")
    parser.add_argument("--cert-dir", type=Path, default=None)
    parser.add_argument("--answers", type=Path, default=None)
    parser.add_argument("--model", choices=("iforest", "lof"), default="iforest")
    args = parser.parse_args(argv)
    try:
        print(evaluate(args.cert_dir, args.answers, model_name=args.model), end="")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Evaluation failed: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
