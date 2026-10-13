"""
Модуль выравнивания угла наклона документа (Deskew / Skew Correction).

Что делает этот модуль:
1. Анализирует ориентацию строк текста на изображении.
2. Определяет угол перекоса (в градусах от -45° до +45°).
3. Применяет аффинное преобразование поворота (cv2.warpAffine), выпрямляя документ
   до строго горизонтального положения строк.

Почему это нужно:
- Пользователи часто сканируют или фотографируют документы криво (под углом 2-15°).
- Нейросети детекции и распознавания текста (OCR) оптимизированы под горизонтальные строки.
  При перекосе даже в 5-7 градусов:
  * Прямоугольные детекторы строк срезают начало и конец строки;
  * Распознавание символов резко падает;
  * Таблицы и колонки ломаются, текст слипается из разных колонок.
- Автоматический deskew возвращает качество OCR обратно на уровень 98-99%.

Алгоритм:
1. Изображение переводится в бинарную маску (текст белый, фон чёрный) через порог Оцу.
2. Находятся координаты всех точек текста (cv2.findNonZero).
3. Вычисляется ориентированный ограничивающий прямоугольник минимальной площади (cv2.minAreaRect).
4. Из угла наклона прямоугольника извлекается угол поворота строк.
5. Матрица аффинного поворота (cv2.getRotationMatrix2D) поворачивает изображение вокруг центра,
   заполняя образующиеся углы белым фоном (cv2.BORDER_CONSTANT, 255).
"""

import logging
from typing import Tuple
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def estimate_skew_angle(image: np.ndarray) -> float:
    """
    Определяет угол наклона строк текста на изображении (в градусах).

    :param image: Изображение OpenCV (BGR или Grayscale).
    :return: Угол наклона в градусах (-45.0 ... 45.0).
             Положительный угол — наклон по часовой стрелке,
             отрицательный — против часовой стрелки.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Размытие по Гауссу для устранения мелкого шума сканирования
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Инвертированная бинаризация по методу Оцу: текст становится белым (255), фон чёрным (0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Морфологическое расширение по горизонтали: склеиваем буквы в цельные строчки
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 3))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    # Находим точки текстовых областей
    points = cv2.findNonZero(dilated)
    if points is None or len(points) < 50:
        logger.debug("Слишком мало текстовых точек для определения угла наклона")
        return 0.0

    # Находим минимальный ориентированный прямоугольник вокруг всех строк
    rect = cv2.minAreaRect(points)
    angle = rect[-1]

    # В OpenCV 4.x угол minAreaRect находится в диапазоне [-90, 0] или [0, 90]
    # Приводим к диапазону [-45, 45]
    if angle < -45.0:
        angle = -(90.0 + angle)
    elif angle > 45.0:
        angle = 90.0 - angle
    else:
        angle = -angle

    # Фильтруем шум: если угол совсем крошечный (< 0.3°), считаем документ ровным
    if abs(angle) < 0.3:
        angle = 0.0

    return float(angle)


def deskew_image(image: np.ndarray, max_angle: float = 45.0) -> Tuple[np.ndarray, float]:
    """
    Выравнивает наклон изображения документа.

    :param image: Исходное изображение (BGR или Grayscale).
    :param max_angle: Максимально допустимый угол коррекции (по умолчанию 45°).
    :return: Кортеж (выровненное_изображение, применённый_угол).
    """
    angle = estimate_skew_angle(image)

    # Если угол равен 0 или превышает предельный максимум (например, повернут боком на 90°),
    # поворот не выполняем (разворот на 90/180/270 выполняет orientation classifier)
    if abs(angle) < 0.3 or abs(angle) > max_angle:
        return image, 0.0

    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    # Матрица аффинного поворота вокруг центра изображения
    # Применяем -angle для компенсации наклона
    rot_matrix = cv2.getRotationMatrix2D(center, -angle, scale=1.0)

    # Выполняем аффинное преобразование с бикубической интерполяцией и белым фоном
    border_color = (255, 255, 255) if len(image.shape) == 3 else 255
    corrected = cv2.warpAffine(
        image,
        rot_matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_color
    )

    logger.info(f"Документ выровнен: скорректирован угол {angle:.2f}°")
    return corrected, round(angle, 2)

