"""
Базовый абстрактный класс для движков OCR (Optical Character Recognition).

Что делает этот модуль:
- Задаёт унифицированный интерфейс (контракт) для любого OCR-движка.
- Определяет структуру распознанного текстового блока (OcrBlock).

Почему это важно (Архитектурный паттерн Strategy):
- В проекте мы используем PaddleOCR, однако в реальном продакшене система должна уметь
  работать с разными движками (Tesseract, EasyOCR, Google Vision API, Яндекс OCR, LayoutLM).
- Благодаря абстракции BaseOcrEngine, остальная часть приложения (FastAPI, Java backend)
  НЕ зависит от конкретной библиотеки PaddleOCR.
- Любой новый OCR-движок подключается за 10 минут реализацией одного метода recognize().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
import numpy as np


@dataclass
class OcrBlock:
    """Структурированный результат распознавания одной текстовой строки/фрагмента."""
    text: str                  # Распознанный текст
    confidence: float          # Достоверность нейросети (0.0 - 1.0)
    bbox: List[int]            # Прямоугольник [x_min, y_min, x_max, y_max] в пикселях
    page: int = 1              # Номер страницы документа


class BaseOcrEngine(ABC):
    """Абстрактный интерфейс движка оптического распознавания текста."""

    @abstractmethod
    def recognize(self, image: np.ndarray, page_num: int = 1) -> List[OcrBlock]:
        """
        Выполняет детекцию и распознавание текста на одном изображении.

        :param image: Изображение в формате OpenCV (BGR или Grayscale, uint8).
        :param page_num: Порядковый номер страницы (для многостраничных PDF).
        :return: Список структурированных текстовых блоков OcrBlock.
        """
        pass

