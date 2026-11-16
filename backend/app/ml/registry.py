from datetime import datetime, timezone
from pathlib import Path
import joblib

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"

def save(model, calibration, feature_columns, directory=None):
    directory = Path(directory) if directory is not None else MODEL_DIR
    directory.mkdir(parents=True, exist_ok=True)
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"{version}.joblib"
    if path.exists():
        raise FileExistsError(f"Model version already exists: {version}")
    joblib.dump({"version": version, "model": model, "calibration": calibration,
                 "feature_columns": list(feature_columns)}, path)
    return version

def load_latest(directory=None):
    directory = Path(directory) if directory is not None else MODEL_DIR
    paths = sorted(directory.glob("*.joblib"))
    if not paths:
        raise FileNotFoundError(f"No trained model found in {directory}; run python -m app.ml.train first")
    return joblib.load(paths[-1])
