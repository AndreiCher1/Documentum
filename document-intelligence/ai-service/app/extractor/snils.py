"""
Экстрактор реквизитов СНИЛС (Страховое свидетельство обязательного пенсионного страхования).

Извлекаемые ключевые поля:
- Страховой номер (СНИЛС, формат: XXX-XXX-XXX YY)
- ФИО застрахованного лица
- Дата рождения
- Место рождения
- Пол
- Дата регистрации в системе обязательного пенсионного страхования
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class SnilsExtractor(BaseFieldExtractor):
    """Экстрактор данных из страхового свидетельства (СНИЛС)."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 1. Номер СНИЛС (11 цифр, формат: XXX-XXX-XXX YY или XXX XXX XXX YY)
        snils_m = re.search(r'\b(\d{3}[\s\-]\d{3}[\s\-]\d{3}[\s\-]\d{2})\b', flat_text)
        if not snils_m:
            # Поиск 11 цифр подряд
            snils_m = re.search(r'\b(\d{11})\b', flat_text)

        if snils_m:
            raw_s = snils_m.group(1).strip()
            digits = re.sub(r'\D', '', raw_s)
            formatted_snils = f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
            bbox, page = find_field_bbox(raw_s, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="snils_number",
                    display_name="Страховой номер СНИЛС",
                    value=formatted_snils,
                    field_type="SNILS",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. ФИО (обычно крупными буквами после заголовка свидетельства)
        fio_found = None
        for i, line in enumerate(lines):
            # Проверяем строку на ФИО из 3 слов (Кириллица)
            words = line.split()
            if len(words) in (2, 3) and all(w.isalpha() and w.isupper() for w in words):
                # Исключаем служебные заголовки
                if not any(k in line for k in ["СТРАХОВОЕ", "СВИДЕТЕЛЬСТВО", "ПЕНСИОННОГО", "ФЕДЕРАЦИИ", "РОССИЙСКАЯ"]):
                    fio_found = line
                    break

        if not fio_found:
            # Резервный поиск по регулярному выражению
            fio_m = re.search(r'\b([А-ЯЁ]{2,}\s+[А-ЯЁ]{2,}(?:\s+[А-ЯЁ]{2,})?)\b', flat_text)
            if fio_m:
                cand = fio_m.group(1).strip()
                if not any(k in cand for k in ["СТРАХОВОЕ", "СВИДЕТЕЛЬСТВО", "ПЕНСИОННОГО", "ФЕДЕРАЦИИ", "РОССИЙСКАЯ"]):
                    fio_found = cand

        if fio_found:
            bbox, page = find_field_bbox(fio_found, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="fio",
                    display_name="ФИО застрахованного лица",
                    value=fio_found,
                    field_type="PERSON_NAME",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Дата рождения
        bdate_m = re.search(r'(?:дата\s*рождения|родился|родилась)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if not bdate_m:
            bdate_m = re.search(r'\b(\d{2}[\.\/]\d{2}[\.\/](?:19\d{2}|20\d{2}))\b', flat_text)

        if bdate_m:
            bdate = bdate_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(bdate, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="birth_date",
                    display_name="Дата рождения",
                    value=bdate,
                    field_type="DATE",
                    confidence=0.94,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Пол
        gender_m = re.search(r'(?:пол)\s*[:\.]?\s*(МУЖ(?:\.|СКОЙ)?|ЖЕН(?:\.|СКИЙ)?)\b', flat_text, re.IGNORECASE)
        if gender_m:
            g_raw = gender_m.group(1).upper()
            gender_val = "МУЖ." if "МУЖ" in g_raw else "ЖЕН."
            bbox, page = find_field_bbox(gender_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="gender",
                    display_name="Пол",
                    value=gender_val,
                    field_type="GENDER",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

        # 5. Место рождения
        place_m = re.search(r'место\s*рождения\s*[:\.]?\s*([А-Яа-я0-9\s\.\,\-]+?)(?=\s*пол|\s*дата\s*регистрации|$)', flat_text, re.IGNORECASE)
        if place_m:
            place_val = place_m.group(1).strip()
            if len(place_val) >= 3:
                bbox, page = find_field_bbox(place_val[:20], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="birth_place",
                        display_name="Место рождения",
                        value=place_val,
                        field_type="TEXT",
                        confidence=0.91,
                        bbox=bbox,
                        page=page
                    )
                )

        # 6. Дата регистрации в ПФР
        reg_m = re.search(r'дата\s*регистрации\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if reg_m:
            reg_date = reg_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(reg_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="registration_date",
                    display_name="Дата регистрации",
                    value=reg_date,
                    field_type="DATE",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        return fields
