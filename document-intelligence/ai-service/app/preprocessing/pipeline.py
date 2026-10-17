"""
Единый конвейер предобработки документов (Preprocessing Pipeline).

Что делает этот класс:
1. Принимает сырые байты файла любого поддерживаемого формата (PDF, PNG, JPG, TIFF, BMP).
2. Определяет тип файла и извлекает страницы в виде матриц OpenCV.
3. Проводит каждую страницу через цепочку преобразований:
   - Анализ качества (резкость, контраст, яркость);
   - Выравнивание перекоса (deskew);
   - Адаптивное улучшение контраста (CLAHE), если контраст снижен.
4. Возвращает структурированный результат со всеми страницами и метриками качества.

Архитектурная роль:
- Изолирует всю сложную логику работы с пикселями, геометрией и форматами файлов
  от слоя OCR и FastAPI endpoints.
- Слой OCR получает на вход уже чистое, ровное и контрастное изображение,
  благодаря чему точность распознавания достигает максимальных показателей.
"""

import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple, Union
import cv2
import numpy as np

from app.preprocessing.pdf_converter import pdf_to_images, pdf_to_pages_data
from app.preprocessing.quality_checker import evaluate_image_quality, QualityMetrics
from app.preprocessing.deskew import deskew_image
from app.preprocessing.enhancer import enhance_document_image

logger = logging.getLogger(__name__)


@dataclass
class PreprocessedPage:
    """Результат предобработки одной страницы документа."""
    page_number: int                 # Номер страницы (1-based)
    original_image: np.ndarray       # Исходное изображение до обработки
    processed_image: np.ndarray      # Финальное выровненное и улучшенное изображение
    quality: QualityMetrics          # Метрики качества
    applied_skew_angle: float        # Угол, на который было повернуто изображение
    ocr_blocks: Optional[List[Any]] = None  # Векторные блоки цифрового слоя (если доступны)


@dataclass
class PreprocessingResult:
    """Полный результат конвейера предобработки."""
    pages: List[PreprocessedPage]    # Все обработанные страницы
    total_pages: int
    is_pdf: bool


class DocumentPreprocessor:
    """Конвейер предобработки входящих документов."""

    def __init__(self, dpi: int = 200, auto_enhance: bool = True):
        self.dpi = dpi
        self.auto_enhance = auto_enhance

    def process(self, file_bytes: bytes, filename: str) -> PreprocessingResult:
        """
        Главный метод обработки файла.

        :param file_bytes: Содержимое файла в байтах.
        :param filename: Имя файла (для определения расширения).
        :return: PreprocessingResult с обработанными страницами.
        """
        filename_lower = filename.lower()
        is_pdf = filename_lower.endswith(".pdf")

        from app.preprocessing.office_converter import OfficeDocumentConverter
        if OfficeDocumentConverter.is_office_document(filename):
            office_pages = OfficeDocumentConverter.process_file(file_bytes, filename)
            processed_pages: List[PreprocessedPage] = []
            for idx, (p_img, p_blocks) in enumerate(office_pages, start=1):
                quality = evaluate_image_quality(p_img)
                prep_page = PreprocessedPage(
                    page_number=idx,
                    original_image=p_img,
                    processed_image=p_img,
                    quality=quality,
                    applied_skew_angle=0.0
                )
                prep_page.ocr_blocks = p_blocks
                processed_pages.append(prep_page)
            return PreprocessingResult(
                pages=processed_pages,
                total_pages=len(processed_pages),
                is_pdf=False
            )

        # 1. Загрузка в список страниц np.ndarray
        pdf_blocks_by_page = []
        if is_pdf:
            raw_pages, pdf_blocks_by_page = pdf_to_pages_data(file_bytes, dpi=self.dpi)
        else:
            # Чтение обычного растрового изображения из буфера байтов
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError(f"Не удалось декодировать изображение: {filename}")
            raw_pages = [img]

        # 2. Обработка каждой страницы через пайплайн
        processed_pages: List[PreprocessedPage] = []

        for idx, page_img in enumerate(raw_pages, start=1):
            logger.info(f"Предобработка страницы {idx}/{len(raw_pages)} ({page_img.shape[1]}x{page_img.shape[0]} px)...")

            # Шаг 2.1: Оценка качества исходного изображения
            quality = evaluate_image_quality(page_img)

            # Шаг 2.2: Выравнивание наклона (Deskew)
            deskewed_img, skew_angle = deskew_image(page_img)

            # Шаг 2.3: Адаптивное улучшение (CLAHE), если контраст понижен
            final_img = deskewed_img
            if self.auto_enhance and quality.is_low_contrast:
                logger.info(f"Контраст страницы {idx} понижен ({quality.contrast}), применяем CLAHE улучшение")
                final_img = enhance_document_image(deskewed_img)

            prep_page = PreprocessedPage(
                page_number=idx,
                original_image=page_img,
                processed_image=final_img,
                quality=quality,
                applied_skew_angle=skew_angle
            )
            # Если в PDF есть готовый векторный текстовый слой — используем его напрямую (в 50-100 раз быстрее OCR)
            if is_pdf and (idx - 1) < len(pdf_blocks_by_page) and pdf_blocks_by_page[idx - 1]:
                prep_page.ocr_blocks = pdf_blocks_by_page[idx - 1]
                logger.info(f"Страница {idx} содержит цифровой слой ({len(prep_page.ocr_blocks)} блоков), OCR опущен.")

            processed_pages.append(prep_page)

        return PreprocessingResult(
            pages=processed_pages,
            total_pages=len(processed_pages),
            is_pdf=is_pdf
        )

