"""
AI Service — точка входа FastAPI приложения.

Этот файл создаёт FastAPI-приложение и подключает маршруты.
FastAPI — это современный веб-фреймворк для Python, который:
- Автоматически генерирует документацию API
- Поддерживает асинхронные запросы
- Валидирует данные через Pydantic

Java backend вызывает этот сервис для AI-анализа документов.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.schemas import HealthResponse, AnalyzeResponse, OcrResult, DocumentTypeResult, ExtractedField

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: выполняется при старте и остановке приложения."""
    logger.info("AI Service запускается...")
    logger.info(f"Версия: {settings.APP_VERSION}")
    logger.info(f"Порт: {settings.PORT}")
    # Здесь в будущем будем загружать ML-модели
    logger.info("AI Service готов к работе")
    yield
    logger.info("AI Service останавливается...")


# Создаём приложение FastAPI
app = FastAPI(
    title="Document Intelligence AI Service",
    description="AI-сервис для анализа и распознавания документов",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS — разрешаем запросы от Java backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production ограничить конкретными адресами
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Проверка здоровья сервиса.
    Java backend вызывает этот endpoint, чтобы убедиться,
    что Python AI-сервис запущен и работает.
    """
    return HealthResponse(
        status="healthy",
        models_loaded=False,  # Пока модели не загружены
        ocr_ready=False,      # OCR пока не настроен
        version=settings.APP_VERSION
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(file: UploadFile = File(...)):
    """
    Анализ документа.
    
    На этом этапе (прототип) возвращает заглушку.
    В следующих этапах здесь будет:
    1. OpenCV — предобработка изображения
    2. PaddleOCR — распознавание текста
    3. Классификация — определение типа документа
    4. Извлечение полей — структурированные данные
    """
    start_time = time.time()
    
    logger.info(f"Получен файл для анализа: {file.filename}")
    logger.info(f"MIME тип: {file.content_type}")
    
    # Проверяем, что файл не пустой
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Файл пустой")
    
    file_size = len(content)
    logger.info(f"Размер файла: {file_size} байт")
    
    processing_time = (time.time() - start_time) * 1000  # мс
    
    # Пока возвращаем заглушку — в следующих этапах заменим на реальный AI
    return AnalyzeResponse(
        status="success",
        processing_time_ms=round(processing_time, 2),
        document_type=DocumentTypeResult(
            type="UNKNOWN",
            confidence=0.0
        ),
        ocr_results=[
            OcrResult(
                text="[Прототип] OCR ещё не подключён",
                confidence=0.0,
                bbox=[0, 0, 0, 0]
            )
        ],
        fields=[],
        overall_confidence=0.0,
        message=f"Прототип: файл '{file.filename}' получен ({file_size} байт). AI-анализ будет добавлен на этапе 5."
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

