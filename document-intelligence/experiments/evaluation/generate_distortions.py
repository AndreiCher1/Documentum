"""
Модуль синтетической аугментации и генерации искажений реального мира.

Используется на Этапе 12 (Эксперименты и стресс-тестирование) для оценки
устойчивости (robustness) OCR-пайплайна к артефактам реальной фотосъёмки:
- Размытие от расфокусировки камеры (Defocus / Gaussian Blur)
- Смаз от движения рук (Motion Blur)
- Геометрический перекос и поворот (Skew / Rotation)
- Сенсорный шум матрицы при плохом освещении (Gaussian / Salt & Pepper)
- Неравномерное освещение и тень от смартфона (Shadow Gradient)
- Недостаточная экспозиция / низкий контраст (Low Contrast & Exposure)
"""

import cv2
import numpy as np


def add_gaussian_blur(image: np.ndarray, kernel_size: int = 7, sigma: float = 2.0) -> np.ndarray:
    """Имитация расфокусировки объектива камеры."""
    if kernel_size % 2 == 0:
        kernel_size += 1
    return cv2.GaussianBlur(image, (kernel_size, kernel_size), sigma)


def add_motion_blur(image: np.ndarray, degree: int = 9, angle: float = 30.0) -> np.ndarray:
    """Имитация смазывания изображения из-за дрожания рук при съёмке."""
    # Генерация ядра сдвига
    m = cv2.getRotationMatrix2D((degree / 2, degree / 2), angle, 1)
    kernel = np.diag(np.ones(degree))
    kernel = cv2.warpAffine(kernel, m, (degree, degree))
    kernel_sum = np.sum(kernel)
    if kernel_sum != 0:
        kernel = kernel / kernel_sum
    return cv2.filter2D(image, -1, kernel)


def add_rotation(image: np.ndarray, angle: float = 12.0) -> np.ndarray:
    """Поворот документа на заданный угол с заполнением фона белым цветом."""
    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    # Матрица аффинного поворота
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = np.abs(matrix[0, 0])
    sin = np.abs(matrix[0, 1])

    # Новый размер холста, чтобы документ не обрезался
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    matrix[0, 2] += (new_w / 2) - center[0]
    matrix[1, 2] += (new_h / 2) - center[1]

    # Белый цвет фона (255, 255, 255)
    border_val = (255, 255, 255) if len(image.shape) == 3 else 255
    return cv2.warpAffine(image, matrix, (new_w, new_h), borderValue=border_val)


def add_noise(image: np.ndarray, var: float = 25.0) -> np.ndarray:
    """Добавление аддитивного гауссова шума (шум сенсора камеры в сумерках)."""
    row, col = image.shape[:2]
    mean = 0
    sigma = var ** 0.5

    if len(image.shape) == 3:
        gauss = np.random.normal(mean, sigma, (row, col, 3))
    else:
        gauss = np.random.normal(mean, sigma, (row, col))

    noisy = image.astype(np.float32) + gauss
    return np.clip(noisy, 0, 255).astype(np.uint8)


def add_salt_pepper_noise(image: np.ndarray, amount: float = 0.02) -> np.ndarray:
    """Добавление импульсного шума ('соль и перец')."""
    noisy = image.copy()
    num_salt = int(np.ceil(amount * image.size * 0.5))
    num_pepper = int(np.ceil(amount * image.size * 0.5))

    # Соль (белые пиксели)
    coords = [np.random.randint(0, i - 1, num_salt) for i in image.shape[:2]]
    noisy[tuple(coords)] = 255

    # Перец (чёрные пиксели)
    coords = [np.random.randint(0, i - 1, num_pepper) for i in image.shape[:2]]
    noisy[tuple(coords)] = 0

    return noisy


def add_shadow_gradient(image: np.ndarray) -> np.ndarray:
    """Имитация падения тени от смартфона или руки поверх документа."""
    h, w = image.shape[:2]
    # Создаём диагональный градиент освещённости
    y, x = np.mgrid[0:h, 0:w]
    # Пятно тени в центре-справа
    cx, cy = int(w * 0.6), int(h * 0.4)
    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = np.sqrt(w ** 2 + h ** 2) / 1.8
    shadow_mask = 0.45 + 0.55 * np.clip(dist / max_dist, 0.0, 1.0)

    if len(image.shape) == 3:
        shadow_mask = np.repeat(shadow_mask[:, :, np.newaxis], 3, axis=2)

    result = image.astype(np.float32) * shadow_mask
    return np.clip(result, 0, 255).astype(np.uint8)


def adjust_contrast_brightness(image: np.ndarray, alpha: float = 0.65, beta: int = -20) -> np.ndarray:
    """Снижение контраста и затемнение (недостаточное освещение в комнате)."""
    adjusted = cv2.convertScaleAbs(image, alpha=alpha, beta=beta)
    return adjusted


def apply_distortion(image: np.ndarray, distortion_type: str) -> np.ndarray:
    """
    Применение искажения по имени:
    - 'gaussian_blur': размытие объектива
    - 'motion_blur': смаз от движения
    - 'rotation': перекос угла на 12 градусов
    - 'sensor_noise': шум матрицы
    - 'shadow': пятно тени от смартфона
    - 'low_contrast': недоэкспонированный снимок
    - 'combined': комбинированное ухудшение
    """
    if distortion_type == 'gaussian_blur':
        return add_gaussian_blur(image, kernel_size=9, sigma=2.5)
    elif distortion_type == 'motion_blur':
        return add_motion_blur(image, degree=11, angle=35.0)
    elif distortion_type == 'rotation':
        return add_rotation(image, angle=12.5)
    elif distortion_type == 'sensor_noise':
        return add_noise(image, var=35.0)
    elif distortion_type == 'shadow':
        return add_shadow_gradient(image)
    elif distortion_type == 'low_contrast':
        return adjust_contrast_brightness(image, alpha=0.6, beta=-25)
    elif distortion_type == 'combined':
        # Комплексный стресс-тест: лёгкий поворот + шум + размытие + тень
        res = add_rotation(image, angle=6.0)
        res = add_gaussian_blur(res, kernel_size=5, sigma=1.2)
        res = add_noise(res, var=15.0)
        res = add_shadow_gradient(res)
        return res
    else:
        return image

