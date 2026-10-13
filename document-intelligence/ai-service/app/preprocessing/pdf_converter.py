"""
Модуль конвертации PDF-документов в изображения для компьютерного зрения.

Что делает этот модуль:
- Принимает байты PDF-файла или путь к нему.
- С помощью библиотеки PyMuPDF (fitz) рендерит векторные/текстовые страницы PDF
  в растровые пиксельные карты (pixmap) с заданным разрешением DPI.
- Преобразует пиксели в формат NumPy array (BGR), понятный OpenCV и нейросетям OCR.

Почему это нужно:
- Модели OCR (нейросети обнаружения и распознавания текста) работают исключительно
  с растровыми матрицами пикселей (высота x ширина x каналы цвета).
- Большинство официальных документов (договоры, счета, акты) приходят в формате PDF.
  Без конвертера PDF система не смогла бы проанализировать ни один PDF-документ.

Почему именно PyMuPDF:
- PyMuPDF работает в 5-10 раз быстрее pdf2image/poppler.
- Не требует установки внешних бинарных утилит (poppler-utils) в операционную систему.
- Позволяет рендерить страницы с точным управлением DPI (по умолчанию 200 DPI).
"""

import io
import logging
from typing import List, Union
import numpy as np
import pymupdf  # Официальный современный импорт PyMuPDF

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_source: Union[bytes, str], dpi: int = 200) -> List[np.ndarray]:
    """
    Конвертирует страницы PDF документа в список изображений OpenCV (BGR).

    :param pdf_source: Байты PDF-файла (bytes) или путь к файлу на диске (str).
    :param dpi: Точек на дюйм при рендеринге (DPI).
                72 DPI — экранное (слишком размыто для мелкого текста).
                200 DPI — оптимальный баланс скорости и качества OCR.
                300 DPI — полиграфическое качество (медленнее, но идеальная детализация).
    :return: Список изображений в формате np.ndarray (OpenCV BGR, uint8).
    """
    images: List[np.ndarray] = []

    try:
        if isinstance(pdf_source, bytes):
            doc = pymupdf.open(stream=pdf_source, filetype="pdf")
        else:
            doc = pymupdf.open(pdf_source)

        total_pages = len(doc)
        logger.info(f"Конвертация PDF ({total_pages} стр.) в изображения с DPI={dpi}...")

        # Масштаб для нужного DPI (по умолчанию 72 DPI в PDF, zoom = dpi / 72)
        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)

        for page_idx in range(total_pages):
            page = doc.load_page(page_idx)
            # Рендерим страницу в RGB пиксмап с альфа-каналом или без
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)

            # Получаем буфер байтов и переводим в numpy массив
            img_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height, pixmap.width, pixmap.n
            )

            # Если каналов 3 (RGB), конвертируем в BGR для OpenCV
            if pixmap.n == 3:
                img_bgr = img_array[:, :, ::-1].copy()  # Быстрый переворот каналов RGB -> BGR
            elif pixmap.n == 1:
                # Одноканальное (градации серого) -> 3-канальный BGR
                import cv2
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
            else:
                img_bgr = img_array.copy()

            images.append(img_bgr)
            logger.debug(f"Страница {page_idx + 1}/{total_pages} отрендерена: {img_bgr.shape}")

        doc.close()
        logger.info(f"Успешно сконвертировано {len(images)} страниц PDF.")
        return images

    except Exception as e:
        logger.error(f"Ошибка конвертации PDF в изображения: {str(e)}", exc_info=True)
        raise ValueError(f"Не удалось прочитать PDF документ: {str(e)}") from e

