"""
Pydantic-модели (схемы) для API.

Pydantic — это библиотека для валидации данных в Python.
Она позволяет описать структуру данных как класс,
и автоматически проверяет, что данные соответствуют ожиданиям.

Эти модели определяют формат JSON, который возвращает наш API.
Java backend будет получать ответы именно в таком формате.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Ответ на запрос проверки здоровья сервиса."""
    status: str
    models_loaded: bool
    ocr_ready: bool
    version: str


class OcrResult(BaseModel):
    """Один распознанный текстовый блок."""
    text: str
    confidence: float
    bbox: list[int]  # [x1, y1, x2, y2]


class DocumentTypeResult(BaseModel):
    """Результат определения типа документа."""
    type: str
    confidence: float


class ExtractedField(BaseModel):
    """Одно извлечённое поле документа."""
    name: str
    display_name: str
    value: str
    field_type: str
    confidence: float
    bbox: list[int] | None = None


class AnalyzeResponse(BaseModel):
    """Полный ответ анализа документа."""
    status: str
    processing_time_ms: float
    document_type: DocumentTypeResult
    ocr_results: list[OcrResult]
    fields: list[ExtractedField]
    overall_confidence: float
    message: str | None = None

