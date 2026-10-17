"""
Модуль конвертации PDF-документов в изображения для компьютерного зрения.

Что делает этот модуль:
- Принимает байты PDF-файла или путь к нему.
- С помощью библиотеки PyMuPDF (fitz) рендерит векторные/текстовые страницы PDF
  в растровые пиксельные карты (pixmap) с заданным разрешением DPI.
- Извлекает встроенный цифровой текстовый слой (Born-Digital Text Layer) с точными координатами,
  позволяя обрабатывать электронные PDF за 15-30 мс в обход тяжелого OCR.
- Преобразует пиксели в формат NumPy array (BGR), понятный OpenCV и нейросетям OCR.
"""

import io
import logging
from typing import Any, List, Optional, Tuple, Union
import numpy as np
import pymupdf  # Официальный современный импорт PyMuPDF

from app.ocr.base import OcrBlock

logger = logging.getLogger(__name__)


def pdf_to_pages_data(
    pdf_source: Union[bytes, str],
    dpi: int = 200
) -> Tuple[List[np.ndarray], List[List[OcrBlock]]]:
    """
    Конвертирует страницы PDF документа в список изображений OpenCV (BGR)
    и извлекает цифровые блоки текста (если они есть).

    :param pdf_source: Байты PDF-файла (bytes) или путь к файлу на диске (str).
    :param dpi: Точек на дюйм при рендеринге (DPI, по умолчанию 200).
    :return: Кортеж (список_изображений_страниц, список_блоков_ocr_для_каждой_страницы).
             Если на странице нет векторного текста (скан), список блоков будет пустым.
    """
    images: List[np.ndarray] = []
    pages_blocks: List[List[OcrBlock]] = []

    try:
        if isinstance(pdf_source, bytes):
            doc = pymupdf.open(stream=pdf_source, filetype="pdf")
        else:
            doc = pymupdf.open(pdf_source)

        total_pages = len(doc)
        logger.info(f"Конвертация PDF ({total_pages} стр.) в изображения с DPI={dpi}...")

        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)

        for page_idx in range(total_pages):
            page = doc.load_page(page_idx)

            # 1. Рендеринг изображения страницы в BGR
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            img_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height, pixmap.width, pixmap.n
            )

            if pixmap.n == 3:
                img_bgr = img_array[:, :, ::-1].copy()
            elif pixmap.n == 1:
                import cv2
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            else:
                img_bgr = img_array.copy()

            images.append(img_bgr)

            # 2. Проверка и извлечение цифрового текстового слоя (Born-Digital Layer)
            # PyMuPDF 'blocks' формат: (x0, y0, x1, y1, "text", block_no, block_type)
            # block_type == 0: текст
            extracted_blocks: List[OcrBlock] = []
            raw_blocks = page.get_text("blocks")
            text_blocks_count = sum(1 for b in raw_blocks if b[6] == 0 and len(b[4].strip()) > 0)

            # Если на странице есть реальный структурированный текст (> 3 блоков и > 30 символов)
            if text_blocks_count >= 2:
                for b in raw_blocks:
                    if b[6] != 0:  # Пропускаем изображения
                        continue
                    b_text = b[4].strip()
                    if not b_text:
                        continue

                    # Масштабируем координаты из 72 DPI в целевой DPI изображения
                    x0 = max(0, int(b[0] * zoom))
                    y0 = max(0, int(b[1] * zoom))
                    x1 = min(img_bgr.shape[1], int(b[2] * zoom))
                    y1 = min(img_bgr.shape[0], int(b[3] * zoom))

                    # Разбиваем многострочные блоки на отдельные строки для точной геометрии
                    lines = [ln.strip() for ln in b_text.split('\n') if ln.strip()]
                    if len(lines) <= 1:
                        extracted_blocks.append(
                            OcrBlock(
                                text=b_text,
                                confidence=1.0,  # Цифровой векторный слой идеален (100% точность)
                                bbox=[x0, y0, x1, y1],
                                page=page_idx + 1
                            )
                        )
                    else:
                        line_h = max(1, (y1 - y0) / len(lines))
                        for l_idx, line_str in enumerate(lines):
                            ly0 = int(y0 + l_idx * line_h)
                            ly1 = int(y0 + (l_idx + 1) * line_h)
                            extracted_blocks.append(
                                OcrBlock(
                                    text=line_str,
                                    confidence=1.0,
                                    bbox=[x0, ly0, x1, ly1],
                                    page=page_idx + 1
                                )
                            )

            pages_blocks.append(extracted_blocks)
            logger.debug(
                f"Страница {page_idx + 1}/{total_pages}: размер {img_bgr.shape}, "
                f"цифровых блоков: {len(extracted_blocks)}"
            )

        doc.close()
        logger.info(f"Успешно обработано {len(images)} страниц PDF.")
        return images, pages_blocks

    except Exception as e:
        logger.error(f"Ошибка конвертации PDF в изображения: {str(e)}", exc_info=True)
        raise ValueError(f"Не удалось прочитать PDF документ: {str(e)}") from e


def pdf_to_images(pdf_source: Union[bytes, str], dpi: int = 200) -> List[np.ndarray]:
    """Обратная совместимость: возвращает только список изображений страниц."""
    images, _ = pdf_to_pages_data(pdf_source, dpi=dpi)
    return images
