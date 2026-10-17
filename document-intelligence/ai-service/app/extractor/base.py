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


def normalize_vin(raw_vin: str) -> Optional[str]:
    """
    Нормализация VIN-номера:
    - Удаление пробелов и разделителей
    - Перевод в верхний регистр
    - Замена типичных ошибок OCR (буквы O, Q -> 0, I -> 1 в соответствии с ISO 3779)
    - Проверка и извлечение 17-значного кода
    """
    if not raw_vin:
        return None
    clean = re.sub(r'[\s\.\,\-_\\\/]+', '', str(raw_vin)).upper()
    trans = str.maketrans({'O': '0', 'Q': '0', 'I': '1'})
    clean_trans = clean.translate(trans)
    
    m = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', clean_trans)
    if m:
        return m.group(1)
    if len(clean_trans) == 17 and re.match(r'^[A-HJ-NPR-Z0-9]{17}$', clean_trans):
        return clean_trans
    return None


def find_spatial_field(
    label_regex: str,
    ocr_blocks: Optional[List[Any]],
    value_filter=None,
    strip_suffixes: Optional[List[str]] = None,
    max_horizontal_gap: int = 550,
    max_vertical_gap: int = 85
) -> tuple[Optional[str], Optional[List[int]], int]:
    """
    Универсальный пространственный поиск значения поля по расположению метки:
    1. Проверяет остаток текста в том же блоке OCR после метки (с удалением служебных суффиксов).
    2. Если в том же блоке значения нет, ищет соседний блок справа на той же горизонтальной строке.
    3. Если справа нет подходящего значения, ищет блок непосредственно снизу (для многострочных бланков).
    """
    if not ocr_blocks:
        return None, None, 1

    default_suffixes = ['тс', 'кг', 'см3', 'см', 'см\"', '(vin)', 'vin', 'квт', 'л.с.', '№', 'no', '№o', '№0']
    suffixes = (strip_suffixes or []) + default_suffixes

    for b in ocr_blocks:
        b_text = getattr(b, 'text', '') if hasattr(b, 'text') else str(b)
        b_bbox = getattr(b, 'bbox', None)
        b_page = getattr(b, 'page', 1)

        m = re.search(label_regex, b_text, re.IGNORECASE)
        if not m:
            continue

        # 1. Проверяем остаток в том же блоке
        rem = re.sub(r'^[ :.\-_№#\t\n]+', '', b_text[m.end():]).strip()
        rem_clean = rem
        for sfx in suffixes:
            rem_clean = re.sub(r'^(?:' + re.escape(sfx) + r')\b[:\s,\-_№#]*', '', rem_clean, flags=re.IGNORECASE).strip()

        min_len = 1 if (value_filter and value_filter(rem_clean)) else 2
        if rem_clean and len(rem_clean) >= min_len and (not value_filter or value_filter(rem_clean)):
            return rem_clean, b_bbox, b_page

        if not b_bbox or len(b_bbox) != 4:
            continue

        lx1, ly1, lx2, ly2 = b_bbox
        candidates_right = []
        candidates_below = []

        for ob in ocr_blocks:
            if ob is b:
                continue
            ob_text = getattr(ob, 'text', '') if hasattr(ob, 'text') else str(ob)
            ob_bbox = getattr(ob, 'bbox', None)
            ob_page = getattr(ob, 'page', 1)
            if not ob_bbox or len(ob_bbox) != 4:
                continue

            ox1, oy1, ox2, oy2 = ob_bbox
            y_diff = abs(((oy1 + oy2) / 2) - ((ly1 + ly2) / 2))
            h = max(ly2 - ly1, oy2 - oy1)

            # Сосед справа на той же строке
            if y_diff <= h * 0.8 and ox1 >= lx1 + 30 and (ox1 - lx2) <= max_horizontal_gap:
                t = ob_text.strip(' :.-_№oO')
                if t and (not value_filter or value_filter(t)):
                    candidates_right.append((ox1 - lx2, t, ob_bbox, ob_page))

            # Сосед снизу
            elif oy1 >= ly2 - 10 and oy1 <= ly2 + max_vertical_gap and abs(ox1 - lx1) < 320:
                t = ob_text.strip(' :.-_№oO')
                if t and (not value_filter or value_filter(t)):
                    candidates_below.append((oy1 - ly2, t, ob_bbox, ob_page))

        if candidates_right:
            candidates_right.sort(key=lambda x: x[0])
            _, val, bbox, page = candidates_right[0]
            return val, bbox, page

        if candidates_below:
            candidates_below.sort(key=lambda x: x[0])
            _, val, bbox, page = candidates_below[0]
            return val, bbox, page

    return None, None, 1


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

