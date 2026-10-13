"""
Базовый модуль извлечения полей (Information Extraction).

Что делает этот модуль:
1. Описывает контракт BaseFieldExtractor для извлечения полей документов.
2. Определяет структуру ExtractedFieldValue со значением, типом данных, уверенностью
   и пространственными координатами Bounding Box.
3. Содержит Spatial Bounding Box Matcher — сопоставляет найденные текстовые сущности
   с координатами блоков PaddleOCR, связывая семантику с визуальным представлением.

Почему важна пространственная привязка (Spatial Grounding):
- Пользователю мало видеть "Номер: 123456" в таблице.
- Важно кликнуть на поле и увидеть зелёную рамку прямо на скане/фотографии паспорта или счёта.
- Это обеспечивает прозрачность (Auditable AI) и мгновенный визуальный контроль человеком.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import re
from typing import Any, List, Optional


@dataclass
class ExtractedFieldValue:
    """Извлечённое структурированное поле."""
    name: str                       # Системное имя (fio, series_number, inn, amount)
    display_name: str               # Человекочитаемое название (Серия и номер, ИНН)
    value: str                      # Распознанное строковое значение
    field_type: str                 # Семантический тип: TEXT, DATE, NUMBER, AMOUNT, INN, PERSON
    confidence: float               # Оценка достоверности (0.0 - 1.0)
    bbox: Optional[List[int]] = None # [x1, y1, x2, y2] координаты на странице
    page: int = 1                   # Номер страницы документа


def find_field_bbox(
    val: str,
    ocr_blocks: Optional[List[Any]] = None,
    min_length: int = 3
) -> tuple[Optional[List[int]], int]:
    """
    Пространственный сопоставитель (Spatial Matcher).
    
    Ищет блок OCR, в котором содержится искомое значение (или его ключевая часть),
    и возвращает координаты Bounding Box [x1, y1, x2, y2] и номер страницы.
    """
    if not val or not ocr_blocks:
        return None, 1

    clean_target = re.sub(r'[\s\.\,\-\/\\]+', '', str(val)).lower()
    if len(clean_target) < min_length:
        clean_target = str(val).strip().lower()

    # 1. Точное включение подстроки в очищенном виде
    for block in ocr_blocks:
        block_text = getattr(block, 'text', '') if hasattr(block, 'text') else str(block)
        clean_block = re.sub(r'[\s\.\,\-\/\\]+', '', block_text).lower()
        if clean_target in clean_block:
            bbox = getattr(block, 'bbox', None)
            page = getattr(block, 'page', 1)
            return bbox, page

    # 2. Неполное пословное включение для длинных значений (например, ФИО или название компании)
    tokens = [t for t in re.split(r'\s+', str(val).strip()) if len(t) >= 3]
    if tokens:
        best_match_block = None
        max_matches = 0

        for block in ocr_blocks:
            block_text = (getattr(block, 'text', '') if hasattr(block, 'text') else str(block)).lower()
            matches = sum(1 for t in tokens if t.lower() in block_text)
            if matches > max_matches:
                max_matches = matches
                best_match_block = block

        if best_match_block and max_matches >= 1:
            bbox = getattr(best_match_block, 'bbox', None)
            page = getattr(best_match_block, 'page', 1)
            return bbox, page

    return None, 1


class BaseFieldExtractor(ABC):
    """Абстрактный класс экстрактора полей документа."""

    @abstractmethod
    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        """
        Извлечь поля из распознанного текста и блоков OCR.
        
        :param text: Объединённый полный текст документа.
        :param ocr_blocks: Список блоков распознавания OcrResult с координатами.
        :return: Список извлечённых структурированных полей.
        """
        pass

