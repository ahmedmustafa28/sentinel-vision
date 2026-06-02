"""AI modules package."""

from app.modules.ai_report import ReportService
from app.modules.face_recognition import FaceRecognitionService
from app.modules.yolo_detection import DetectionService
from app.modules.ai_analyst import AIAnalystService

__all__ = ["DetectionService", "FaceRecognitionService", "ReportService", "AIAnalystService"]
