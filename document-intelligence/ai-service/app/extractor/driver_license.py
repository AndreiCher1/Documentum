"""
Экстрактор реквизитов Водительского удостоверения (Driver's License).

Извлекаемые ключевые поля:
- 1. Фамилия
- 2. Имя и Отчество
- 3. Дата рождения
- 4a. Дата выдачи
- 4b. Дата окончания срока действия (10 лет)
- 4c. Кем выдано (ГИБДД)
- 5. Номер удостоверения (серия и номер: 2 цифры 2 цифры 6 цифр, e.g. 77 12 345678)
- 8. Регион / Место жительства
- 9. Открытые категории ТС (A, B, C, D, BE, CE...)
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class DriverLicenseExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из водительского удостоверения РФ."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Серия и номер удостоверения (формат: 4 цифры + 6 цифр, например 77 20 123456 или 7720 123456)
        num_m = re.search(r'(?:5\.?\s*)?(\d{2}\s*\d{2}\s*\d{6})\b', flat_text)
        if not num_m:
            num_m = re.search(r'\b(\d{10})\b', flat_text)

        if num_m:
            raw_n = num_m.group(1).strip()
            digits = re.sub(r'\D', '', raw_n)
            formatted_num = f"{digits[:2]} {digits[2:4]} {digits[4:]}"
            bbox, page = find_field_bbox(raw_n, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="license_number",
                    display_name="Номер удостоверения",
                    value=formatted_num,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. Фамилия (графа 1)
        last_name_m = re.search(r'1\.\s*([А-ЯЁA-Z\s\-]+?)(?=\s*2\.|\s*ИМЯ|$)', flat_text, re.IGNORECASE)
        if last_name_m:
            ln_val = last_name_m.group(1).strip()
            # Берем первое русское слово
            rus_words = [w for w in ln_val.split() if re.match(r'^[А-ЯЁа-яё\-]+$', w)]
            if rus_words:
                last_name_clean = rus_words[0].upper()
                bbox, page = find_field_bbox(last_name_clean, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="last_name",
                        display_name="Фамилия",
                        value=last_name_clean,
                        field_type="PERSON_NAME",
                        confidence=0.95,
                        bbox=bbox,
                        page=page
                    )
                )

        # 3. Имя и Отчество (графа 2)
        first_name_m = re.search(r'2\.\s*([А-ЯЁA-Z\s\-]+?)(?=\s*3\.|\s*ДАТА|$)', flat_text, re.IGNORECASE)
        if first_name_m:
            fn_val = first_name_m.group(1).strip()
            rus_words = [w for w in fn_val.split() if re.match(r'^[А-ЯЁа-яё\-]+$', w)]
            if rus_words:
                first_name_clean = " ".join(rus_words).upper()
                bbox, page = find_field_bbox(rus_words[0].upper(), ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="first_name",
                        display_name="Имя и Отчество",
                        value=first_name_clean,
                        field_type="PERSON_NAME",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )

        # 4. Дата рождения (графа 3)
        bdate_m = re.search(r'3\.\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
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
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 5. Дата выдачи (графа 4a)
        issue_m = re.search(r'4a\)?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if issue_m:
            issue_date = issue_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(issue_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="issue_date",
                    display_name="Дата выдачи",
                    value=issue_date,
                    field_type="DATE",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. Дата окончания действия (графа 4b)
        exp_m = re.search(r'4b\)?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if exp_m:
            exp_date = exp_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(exp_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="expiration_date",
                    display_name="Срок действия",
                    value=exp_date,
                    field_type="DATE",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 7. Подразделение ГИБДД (графа 4c)
        dept_m = re.search(r'4c\)?\s*([А-Яа-яA-Za-z0-9\s]+?)(?=\s*5\.|\s*6\.|$)', flat_text, re.IGNORECASE)
        if dept_m:
            dept_val = dept_m.group(1).strip()
            if len(dept_val) >= 2:
                bbox, page = find_field_bbox(dept_val[:10], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="issuing_authority",
                        display_name="Орган выдачи (ГИБДД)",
                        value=dept_val,
                        field_type="TEXT",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 8. Открытые категории ТС (графа 9)
        cats_m = re.findall(r'\b(A1|A|B1|BE|B|C1E|C1|CE|C|D1E|D1|DE|D|M|TM|TB)\b', flat_text)
        if cats_m:
            unique_cats = sorted(list(set(cats_m)))
            cats_str = ", ".join(unique_cats)
            fields.append(
                ExtractedFieldValue(
                    name="categories",
                    display_name="Категории ТС",
                    value=cats_str,
                    field_type="TEXT",
                    confidence=0.93,
                    bbox=[0, 0, 0, 0],
                    page=1
                )
            )

        return fields

