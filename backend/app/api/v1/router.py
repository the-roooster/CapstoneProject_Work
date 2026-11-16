from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_analyst
from app.api.v1 import alerts, events, jobs, users
from app.ml.registry import load_latest

router = APIRouter(dependencies=[Depends(get_current_analyst)])
router.include_router(users.router)
router.include_router(events.router)
router.include_router(alerts.router)
router.include_router(jobs.router)


@router.get("/meta", tags=["meta"])
def meta():
    try:
        artifact = load_latest()
    except FileNotFoundError:
        raise HTTPException(503, "No trained model available")
    calibration = artifact["calibration"]
    return {"model_version": artifact["version"], "medium_cut": calibration.med_cut,
            "high_cut": calibration.high_cut, "scale": {"medium": 40, "high": 70}}
