"""
Модуль адаптивного улучшения изображения документа (Image Enhancer).

Что делает этот модуль:
1. Применяет адаптивную эквализацию гистограммы с ограничением контраста (CLAHE).
2. Выравнивает освещение при наличии неравномерных теней от смартфона.
3. Очищает цифровой шум и артефакты сканирования с помощью двустороннего фильтра (Bilateral Filter),
   который сглаживает фон, сохраняя при этом резкие грани букв.

Почему это нужно:
- Реальные документы приходят в плачевном состоянии:
  * Блеклые копии и старые чеки;
  * Сканы со смазанным серым фоном вместо белого листа;
  * Фотографии со смартфона с тенью от руки в углу страницы.
- Стандартное глобальное повышение контраста пересвечивает яркие участки и делает чёрными тени.
- Алгоритм CLAHE работает локальными плитками (grid 8x8):
  * Вытягивает детали в тёмных участках;
  * Не даёт раздувать шум (за счёт clipLimit=2.0);
  * Делает текст чётким чёрным на чистом белом фоне.
"""

import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def apply_clahe(image: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple = (8, 8)) -> np.ndarray:
    """
    Применяет алгоритм CLAHE (Contrast Limited Adaptive Histogram Equalization).

    Для цветных изображений преобразование выполняется только в L-канале
    пространства цветов LAB, сохраняя естественные оттенки печатей и подписей.

    :param image: Входное изображение OpenCV (BGR или Grayscale).
    :param clip_limit: Порог ограничения контраста (предотвращает усиление шума).
    :param tile_grid_size: Размер локального окна для гистограммы.
    :return: Улучшенное изображение того же формата.
    """
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    if len(image.shape) == 3:
        # Переводим в цветовое пространство LAB (L = Яркость, A/B = Цветность)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # Выравниваем только яркостную составляющую (L)
        enhanced_l = clahe.apply(l_channel)

        # Собираем обратно
        merged_lab = cv2.merge((enhanced_l, a_channel, b_channel))
        enhanced_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
        return enhanced_bgr
    else:
        # Grayscale
        return clahe.apply(image)


def denoise_document(image: np.ndarray) -> np.ndarray:
    """
    Подавляет шум сканирования без потери чёткости контуров букв.

    Использует Bilateral Filter — нелинейный фильтр, учитывающий как
    пространственную близость пикселей, так и фотометрическую разницу.
    В отличие от Gaussian Blur, Bilateral НЕ размывает границы текста!
    """
    if len(image.shape) == 3:
        return cv2.bilateralFilter(image, d=5, sigmaColor=50, sigmaSpace=50)
    else:
        return cv2.bilateralFilter(image, d=5, sigmaColor=50, sigmaSpace=50)


def enhance_document_image(image: np.ndarray, apply_denoise: bool = False) -> np.ndarray:
    """
    Комплексное улучшение качества изображения документа.

    :param image: Исходное изображение (BGR).
    :param apply_denoise: Включать ли шумоподавление.
    :return: Обработанное контрастное изображение.
    """
    result = image

    if apply_denoise:
        result = denoise_document(result)

    result = apply_clahe(result, clip_limit=2.0)
    return result

