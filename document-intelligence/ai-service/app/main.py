"""
AI Service — главная точка входа FastAPI приложения.

Архитектурная роль:
- Принимает HTTP-запросы от Java backend.
- Реализует сквозной ML/CV конвейер:
  1. Предобработка: рендеринг PDF, детекция резкости/размытия, выравнивание перекоса (deskew), CLAHE.
  2. OCR: детекция и распознавание текста нейросетью PaddleOCR (PP-OCRv5).
- Возвращает структурированный JSON с координатами bounding boxes, текстом и метриками качества.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.schemas import (
    HealthResponse,
    AnalyzeResponse,
    OcrResult,
    DocumentTypeResult,
    ExtractedField,
    QualityMetricsDto
)
from app.preprocessing.pipeline import DocumentPreprocessor
from app.ocr.factory import get_ocr_engine
from app.classifier.factory import get_document_classifier
from app.extractor.factory import get_field_extractor
from app.table import TableExtractor
from app.postprocessing.spell_corrector import spell_corrector
from app.validation.engine import validation_engine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл сервиса: прогрев и инициализация ML-моделей при старте."""
    logger.info("AI Service запускается...")
    logger.info(f"Версия: {settings.APP_VERSION}, Порт: {settings.PORT}")

    try:
        # Прогрев OCR-моделей при старте приложения (чтобы первый пользовательский запрос не ждал)
        engine = get_ocr_engine()
        if engine.is_ready:
            logger.info("ML-модели PaddleOCR успешно прогреты и готовы к обработке документов!")
        else:
            logger.warning("OCR-движок инициализирован с предупреждением (будет повтор при первом запросе)")
    except Exception as e:
        logger.error(f"Ошибка предварительной загрузки моделей: {e}", exc_info=True)

    yield
    logger.info("AI Service останавливается...")


# Создаём приложение FastAPI
app = FastAPI(
    title="Document Intelligence AI Service",
    description="Интеллектуальный сервис компьютерного зрения и OCR для анализа документов",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS — разрешаем вызовы от Java backend и Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Проверка здоровья сервиса.
    Java backend вызывает этот endpoint для мониторинга готовности OCR.
    """
    engine = get_ocr_engine()
    is_ready = engine.is_ready if engine else False

    return HealthResponse(
        status="healthy" if is_ready else "degraded",
        models_loaded=is_ready,
        ocr_ready=is_ready,
        version=settings.APP_VERSION
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(file: UploadFile = File(...)):
    """
    Полный анализ документа:
    1. Чтение и валидация файла.
    2. Предобработка: PyMuPDF (для PDF), OpenCV deskew, оценка резкости, CLAHE.
    3. Распознавание текста нейросетью PaddleOCR (детекция блоков + OCR).
    4. Формирование структурированного ответа с координатами Bounding Boxes.
    """
    start_time = time.time()
    filename = file.filename or "unknown_document"
    logger.info(f"Получен файл для анализа: {filename} (тип: {file.content_type})")

    content = await file.read()
    if not content or len(content) == 0:
        raise HTTPException(status_code=400, detail="Файл пустой")

    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Размер файла превышает лимит (50 МБ)")

    # 1. Запуск конвейера предобработки
    try:
        preprocessor = DocumentPreprocessor(dpi=200, auto_enhance=True)
        prep_result = preprocessor.process(content, filename)
    except Exception as e:
        logger.error(f"Ошибка предобработки документа '{filename}': {str(e)}", exc_info=True)
        raise HTTPException(status_code=422, detail=f"Ошибка предобработки документа: {str(e)}")

    if not prep_result.pages:
        raise HTTPException(status_code=422, detail="Не удалось извлечь ни одной страницы из документа")

    # 2. Оптическое распознавание текста (OCR) для каждой страницы
    ocr_engine = get_ocr_engine()
    all_ocr_results: list[OcrResult] = []

    for page in prep_result.pages:
        try:
            page_blocks = ocr_engine.recognize(page.processed_image, page_num=page.page_number)
            for block in page_blocks:
                all_ocr_results.append(
                    OcrResult(
                        text=block.text,
                        confidence=block.confidence,
                        bbox=block.bbox,
                        page=block.page
                    )
                )
        except Exception as e:
            logger.error(f"Ошибка OCR страницы {page.page_number}: {str(e)}", exc_info=True)
            # Не обрываем весь документ, если упала отдельная страница
            continue

    # 2.5. Умная коррекция опечаток OCR и нормализация слов русского языка (Этап 9: Lexical Normalization)
    all_ocr_results = spell_corrector.correct_blocks(all_ocr_results)

    # 3. Расчёт базовой уверенности OCR
    if all_ocr_results:
        avg_ocr_conf = sum(b.confidence for b in all_ocr_results) / len(all_ocr_results)
    else:
        avg_ocr_conf = 0.0

    # 4. Классификация документа (Этап 6: Hybrid Ensemble Classifier)
    full_text = "\n".join(b.text for b in all_ocr_results)
    classifier = get_document_classifier()
    class_result = classifier.classify(full_text, all_ocr_results)

    logger.info(
        f"Классификация '{filename}': {class_result.predicted_type} "
        f"({class_result.display_name}) [уверенность: {class_result.confidence:.1%}]"
    )

    # 5. Извлечение структурированных полей (Этап 7: Information Extraction)
    extractor = get_field_extractor(class_result.predicted_type)
    raw_fields = extractor.extract(full_text, all_ocr_results)

    extracted_fields: list[ExtractedField] = []
    for f in raw_fields:
        extracted_fields.append(
            ExtractedField(
                name=f.name,
                display_name=f.display_name,
                value=f.value,
                field_type=f.field_type,
                confidence=round(f.confidence, 4),
                bbox=f.bbox,
                page=f.page
            )
        )

    logger.info(f"Извлечено структурированных полей: {len(extracted_fields)}")

    # 5.1 Извлечение таблиц и сложных структур (Этап 8: Document Understanding)
    table_extractor = TableExtractor()
    extracted_tables = table_extractor.extract_tables(
        images=[p.processed_image for p in prep_result.pages],
        ocr_blocks=all_ocr_results
    )
    for tbl in extracted_tables:
        t_title = f"Таблица {tbl.table_id}" if len(extracted_tables) > 1 else "Таблица товаров и услуг"
        extracted_fields.append(
            ExtractedField(
                name=f"table_{tbl.table_id}",
                display_name=t_title,
                value=table_extractor.to_field_value(tbl),
                field_type="TABLE",
                confidence=round(tbl.confidence, 4),
                bbox=tbl.bbox,
                page=tbl.page
            )
        )
    if extracted_tables:
        logger.info(f"Извлечено таблиц: {len(extracted_tables)}")

    # 5.2 Валидация бизнес-правил документа (Этап 9: Business Rules Validation)
    val_report = validation_engine.validate(
        document_type=class_result.predicted_type,
        fields=extracted_fields,
        tables=extracted_tables
    )

    # 6. Расчёт итоговой уверенности (Overall Confidence)
    if extracted_fields:
        avg_fields_conf = sum(f.confidence for f in extracted_fields) / len(extracted_fields)
        overall_conf = 0.35 * avg_ocr_conf + 0.35 * class_result.confidence + 0.30 * avg_fields_conf
    elif all_ocr_results:
        overall_conf = 0.50 * avg_ocr_conf + 0.50 * class_result.confidence
    else:
        overall_conf = 0.0

    # Метрики качества первой страницы
    first_page_quality = prep_result.pages[0].quality
    quality_dto = QualityMetricsDto(
        blur_score=first_page_quality.blur_score,
        is_blurry=first_page_quality.is_blurry,
        brightness=first_page_quality.brightness,
        contrast=first_page_quality.contrast,
        width=first_page_quality.width,
        height=first_page_quality.height,
        skew_angle=prep_result.pages[0].applied_skew_angle
    )

    processing_time_ms = round((time.time() - start_time) * 1000, 2)
    logger.info(
        f"Анализ '{filename}' завершён за {processing_time_ms} мс. "
        f"Страниц: {prep_result.total_pages}, блоков OCR: {len(all_ocr_results)}, "
        f"полей: {len(extracted_fields)}, таблиц: {len(extracted_tables)}, итоговая уверенность: {overall_conf:.2%}"
    )

    return AnalyzeResponse(
        status="success",
        processing_time_ms=processing_time_ms,
        total_pages=prep_result.total_pages,
        quality=quality_dto,
        document_type=DocumentTypeResult(
            type=class_result.predicted_type,
            confidence=round(class_result.confidence, 4),
            display_name=class_result.display_name,
            explanation=class_result.explanation,
            matched_keywords=class_result.matched_keywords
        ),
        ocr_results=all_ocr_results,
        fields=extracted_fields,
        tables=[tbl.model_dump() for tbl in extracted_tables],
        validation=val_report.model_dump(),
        overall_confidence=round(overall_conf, 4),
        message=(
            f"Определён тип: {class_result.display_name}. "
            f"Распознано {len(all_ocr_results)} блоков OCR, извлечено {len(extracted_fields)} полей "
            f"и {len(extracted_tables)} таблиц. Проверка правил: {val_report.overall_status} "
            f"({val_report.passed_rules}/{val_report.total_rules} пройдено)."
        )
    )


@app.post("/render-page")
async def render_page_image(
    file: UploadFile = File(...),
    page: int = 1,
    dpi: int = 150
):
    """
    Рендерит страницу документа (PDF или обычное изображение) в PNG-картинку.
    Позволяет комфортно просматривать многостраничные PDF в веб-интерфейсе.
    """
    content = await file.read()
    filename = (file.filename or "").lower()
    from fastapi.responses import Response

    if filename.endswith(".pdf"):
        import pymupdf
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            page_idx = max(0, min(page - 1, len(doc) - 1))
            p = doc.load_page(page_idx)
            zoom = dpi / 72.0
            pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            png_bytes = pix.tobytes("png")
            doc.close()
            return Response(content=png_bytes, media_type="image/png")
        except Exception as e:
            logger.error(f"Ошибка рендеринга страницы PDF: {e}")
            raise HTTPException(status_code=500, detail=f"Ошибка рендеринга страницы PDF: {str(e)}")
    else:
        return Response(content=content, media_type=file.content_type or "image/png")


@app.post("/experiments/run")
async def run_experiments(quick_mode: bool = True):
    """
    Запуск стресс-тестирования моделей и расчёта метрик (CER, WER, F1, точность).
    """
    import sys
    from pathlib import Path
    exp_dir = Path(__file__).resolve().parent.parent.parent / "experiments"
    if str(exp_dir) not in sys.path:
        sys.path.insert(0, str(exp_dir))
    from evaluation.benchmark_engine import benchmark_engine
    try:
        results = benchmark_engine.run_benchmark(quick_mode=quick_mode)
        return results
    except Exception as e:
        logger.error(f"Ошибка выполнения эксперимента: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка бенчмарка: {str(e)}")


@app.get("/experiments/latest")
async def get_latest_experiments():
    """
    Получение результатов последнего сохранённого эксперимента.
    """
    import json
    from pathlib import Path
    res_path = Path(__file__).resolve().parent.parent.parent / "experiments" / "results" / "benchmark_results.json"
    if not res_path.exists():
        return {
            "status": "not_run",
            "summary": {
                "mean_baseline_cer": 0.0,
                "mean_enhanced_cer": 0.0,
                "mean_baseline_wer": 0.0,
                "mean_enhanced_wer": 0.0,
                "mean_baseline_f1": 0.0,
                "mean_enhanced_f1": 0.0,
                "mean_baseline_accuracy": 0.0,
                "mean_enhanced_accuracy": 0.0,
                "mean_enhanced_latency_ms": 0.0,
                "cer_reduction_pct": 0.0,
                "f1_gain_pct": 0.0,
                "total_tested_samples": 0,
                "conditions_count": 0,
                "timestamp": "Никогда"
            },
            "table": []
        }
    try:
        with open(res_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения результатов: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
