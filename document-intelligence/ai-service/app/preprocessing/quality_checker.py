"""
Модуль проверки качества входного изображения (Quality Checker).

Что делает этот модуль:
1. Оценивает степень резкости (фокусировки) документа через дисперсию Лапласиана (Laplacian Variance).
2. Вычисляет среднюю яркость (Brightness) и контрастность (Contrast).
3. Определяет разрешение (ширину, высоту, мегапиксели).
4. Выставляет флаг `is_blurry`, если изображение слишком размыто для надёжного распознавания.

Почему это нужно:
- Если документ сфотографирован на телефон в темноте со смазанным фокусом,
  OCR либо вернёт мусор (галлюцинации), либо не увидит текст.
- Детектор качества позволяет заранее предупредить пользователя:
  "Документ слишком размыт, качество распознавания может быть снижено!"

Математика резкости:
- Оператор Лапласа (cv2.Laplacian) вычисляет вторую производную изображения,
  подчёркивая резкие перепады яркости (границы символов текста).
- Дисперсия (variance) отклика Лапласа:
  * В резком документе перепады границ огромные -> дисперсия высока (> 100).
  * В размытом документе границы сглажены -> дисперсия низкая (< 80-100).
"""

import logging
from dataclasses import dataclass
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Пороговые значения качества
BLUR_THRESHOLD = 90.0          # Ниже этого значения — изображение размыто
LOW_CONTRAST_THRESHOLD = 35.0  # Ниже этого — блеклый серый скан
MIN_RECOMMENDED_WIDTH = 600    # Минимальная рекомендуемая ширина для OCR


@dataclass
class QualityMetrics:
    """Метрики качества изображения документа."""
    blur_score: float         # Дисперсия Лапласиана (чем выше, тем резче)
    is_blurry: bool           # True, если blur_score < BLUR_THRESHOLD
    brightness: float         # Средняя яркость (0-255)
    contrast: float           # Стандартное отклонение яркости (контраст)
    is_low_contrast: bool     # True, если contrast < LOW_CONTRAST_THRESHOLD
    width: int                # Ширина в пикселях
    height: int               # Высота в пикселях
    megapixels: float         # Разрешение в мегапикселях


def evaluate_image_quality(image: np.ndarray) -> QualityMetrics:
    """
    Вычисляет объективные метрики качества для входного изображения документа.

    :param image: Изображение в формате OpenCV (BGR или Grayscale, uint8).
    :return: QualityMetrics с рассчитанными показателями.
    """
    if image is None or image.size == 0:
        raise ValueError("Пустое изображение передано в evaluate_image_quality")

    height, width = image.shape[:2]
    megapixels = round((width * height) / 1_000_000.0, 2)

    # Приводим к оттенкам серого для спектрального/градиентного анализа
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 1. Оценка резкости через оператор Лапласа (CV_64F для предотвращения переполнения)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(laplacian.var())

    # 2. Оценка яркости (среднее значение пикселей)
    brightness = float(np.mean(gray))

    # 3. Оценка контраста (стандартное отклонение пикселей)
    contrast = float(np.std(gray))

    is_blurry = blur_score < BLUR_THRESHOLD
    is_low_contrast = contrast < LOW_CONTRAST_THRESHOLD

    logger.debug(
        f"Метрики качества: резкость={blur_score:.1f} (blurry={is_blurry}), "
        f"яркость={brightness:.1f}, контраст={contrast:.1f}, размер={width}x{height}"
    )

    return QualityMetrics(
        blur_score=round(blur_score, 2),
        is_blurry=is_blurry,
        brightness=round(brightness, 2),
        contrast=round(contrast, 2),
        is_low_contrast=is_low_contrast,
        width=width,
        height=height,
        megapixels=megapixels
    )

