from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.db.crud_camera import create_camera, update_camera, get_camera_by_id
from app.schemas.camera import CameraCreate, CameraUpdate, CameraResponse

router = APIRouter()


@router.post("/cameras", response_model=CameraResponse, status_code=status.HTTP_201_CREATED, summary="Create a new camera")
def api_create_camera(camera_in: CameraCreate, db: Session = Depends(get_db_session)):
    """Creates a new camera after validation."""
    camera = create_camera(
        db,
        name=camera_in.name,
        source_url=camera_in.source_url,
        location=camera_in.location,
        is_active=camera_in.is_active if camera_in.is_active is not None else True,
        is_restricted=camera_in.is_restricted if camera_in.is_restricted is not None else False,
    )
    return camera


@router.put("/cameras/{camera_id}", response_model=CameraResponse, summary="Update an existing camera")
def api_update_camera(camera_id: int, camera_in: CameraUpdate, db: Session = Depends(get_db_session)):
    """Updates an existing camera's configurations after validation."""
    camera = get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    updated = update_camera(
        db,
        camera_id=camera_id,
        name=camera_in.name,
        source_url=camera_in.source_url,
        location=camera_in.location,
        is_active=camera_in.is_active,
        is_restricted=camera_in.is_restricted,
    )
    return updated
