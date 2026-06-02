from sqlalchemy.orm import Session

from app.models.camera import Camera


def create_camera(
    db: Session,
    *,
    name: str,
    source_url: str,
    location: str | None = None,
    is_active: bool = True,
    is_restricted: bool = False,
) -> Camera:
    camera = Camera(
        name=name,
        source_url=source_url,
        location=location,
        is_active=is_active,
        is_restricted=is_restricted,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def get_camera_by_id(db: Session, camera_id: int) -> Camera | None:
    return db.query(Camera).filter(Camera.id == camera_id).first()


def list_cameras(db: Session, skip: int = 0, limit: int = 100) -> list[Camera]:
    return db.query(Camera).offset(skip).limit(limit).all()


def update_camera(
    db: Session,
    *,
    camera_id: int,
    name: str | None = None,
    source_url: str | None = None,
    location: str | None = None,
    is_active: bool | None = None,
    is_restricted: bool | None = None,
) -> Camera | None:
    camera = get_camera_by_id(db, camera_id)
    if camera is None:
        return None

    if name is not None:
        camera.name = name
    if source_url is not None:
        camera.source_url = source_url
    if location is not None:
        camera.location = location
    if is_active is not None:
        camera.is_active = is_active
    if is_restricted is not None:
        camera.is_restricted = is_restricted

    db.commit()
    db.refresh(camera)
    return camera


def delete_camera(db: Session, camera_id: int) -> bool:
    camera = get_camera_by_id(db, camera_id)
    if camera is None:
        return False

    db.delete(camera)
    db.commit()
    return True
