from fastapi import APIRouter, Header, HTTPException, Depends, status
from pathlib import Path
from app.core.config import get_settings, Settings
from app.jobs.retention_job import run_retention_cleanup, BASE_DIR

router = APIRouter()


@router.post("/admin/run-retention", status_code=status.HTTP_200_OK, summary="Manually trigger retention cleanup")
def api_run_retention(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
    settings: Settings = Depends(get_settings)
):
    """
    Manually triggers the event logs and snapshot image files retention cleanup.
    Requires header X-Admin-Key matching the SECRET_KEY env configuration.
    """
    if x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin Key"
        )

    snapshot_dir = (BASE_DIR / settings.event_snapshot_dir).resolve()
    result = run_retention_cleanup(settings.event_retention_days, snapshot_dir)
    return {
        "status": "success",
        "message": "Retention cleanup completed successfully.",
        "details": result
    }
