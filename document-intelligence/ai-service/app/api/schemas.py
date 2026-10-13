"""
Pydantic-модели (схемы) для API.

Pydantic — это библиотека для валидации данных в Python.
Она позволяет описать структуру данных как класс,
и автоматически проверяет, что данные соответствуют ожиданиям.

Эти модели определяют формат JSON, который возвращает наш API.
Java backend будет получать ответы именно в таком формате.
"""

from typing import List, Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Ответ на запрос проверки здоровья сервиса."""
    status: str
    models_loaded: bool
    ocr_ready: bool
    version: str


class QualityMetricsDto(BaseModel):
    """Метрики качества изображения документа."""
    blur_score: float
    is_blurry: bool
    brightness: float
    contrast: float
    width: int
    height: int
    skew_angle: float


class OcrResult(BaseModel):
    """Один распознанный текстовый блок (строка или фрагмент текста)."""
    text: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]
    page: int = 1    # Номер страницы документа


class DocumentTypeResult(BaseModel):
    """Результат определения типа документа."""
    type: str
    confidence: float
    display_name: Optional[str] = None
    explanation: Optional[str] = None
    matched_keywords: Optional[List[str]] = None


class ExtractedField(BaseModel):
    """Одно извлечённое поле документа."""
    name: str
    display_name: str
    value: str
    field_type: str
    confidence: float
    bbox: Optional[List[int]] = None
    page: int = 1


class AnalyzeResponse(BaseModel):
    """Полный ответ анализа документа."""
    status: str
    processing_time_ms: float
    total_pages: int = 1
    quality: Optional[QualityMetricsDto] = None
    document_type: DocumentTypeResult
    ocr_results: List[OcrResult]
    fields: List[ExtractedField]
    tables: Optional[List[dict]] = None
    validation: Optional[dict] = None
    overall_confidence: float
    message: Optional[str] = None
