"""
Фабрика OCR-движков (OCR Factory).

Что делает этот модуль:
- Создаёт и кэширует единственный экземпляр OCR-движка (паттерн Singleton).
- Изолирует процесс создания и настройки нейросетевых моделей.

Почему это важно:
- Модели нейросетей PaddleOCR занимают десятки мегабайт в оперативной памяти
  и их инициализация (парсинг весов, компиляция графов вычислений) занимает 2-5 секунд.
- Создавать новый экземпляр PaddleOCR на каждый входящий HTTP-запрос — грубая архитектурная ошибка.
- Singleton-фабрика гарантирует, что модели загружаются ровно ОДИН раз при старте сервера
  и повторно используются для всех последующих запросов.
"""

import logging
from typing import Optional
from app.ocr.base import BaseOcrEngine
from app.ocr.paddle_engine import PaddleOcrEngine

logger = logging.getLogger(__name__)

_ocr_engine_instance: Optional[BaseOcrEngine] = None


def get_ocr_engine() -> BaseOcrEngine:
    """
    Возвращает синглтон-экземпляр OCR-движка.
    """
    global _ocr_engine_instance
    if _ocr_engine_instance is None:
        logger.info("Инициализация глобального OCR-движка...")
        _ocr_engine_instance = PaddleOcrEngine(lang="ru", use_angle_cls=True)
    return _ocr_engine_instance

