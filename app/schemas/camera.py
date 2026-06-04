from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    source_url: str = Field(..., min_length=1, max_length=500)
    location: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = True
    is_restricted: Optional[bool] = False

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, v: str) -> str:
        from app.core.validators import validate_camera_source

        try:
            res = validate_camera_source(v)
            return str(res)
        except ValueError as exc:
            raise ValueError(
                "Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed"
            ) from exc


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    source_url: Optional[str] = Field(default=None, min_length=1, max_length=500)
    location: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None
    is_restricted: Optional[bool] = None

    @field_validator("source_url")
    @classmethod
    def validate_source(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.core.validators import validate_camera_source

        try:
            res = validate_camera_source(v)
            return str(res)
        except ValueError as exc:
            raise ValueError(
                "Invalid camera source: only rtsp/rtsps/http/https schemes or integer device indices are allowed"
            ) from exc


class CameraResponse(BaseModel):
    id: int
    name: str
    source_url: str
    location: Optional[str] = None
    is_active: bool
    is_restricted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
