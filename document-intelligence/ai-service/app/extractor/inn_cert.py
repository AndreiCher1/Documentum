"""
Экстрактор реквизитов Свидетельства о постановке на учёт в налоговом органе (ИНН).

Извлекаемые ключевые поля:
- Идентификационный номер налогоплательщика (ИНН: 10 или 12 цифр)
- ФИО налогоплательщика (или наименование организации)
- Дата постановки на учёт
- Наименование налогового органа (ИФНС)
- Код налогового органа
- Серия и номер бланка
- ОГРНИП / ОГРН (при наличии)
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class InnCertificateExtractor(BaseFieldExtractor):
    """Экстрактор свидетельства ИНН."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Номер ИНН (10 цифр для ЮЛ, 12 цифр для ФЛ)
        inn_m = re.search(r'(?:инн|налогоплательщика)\s*[:\.]?\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE)
        if not inn_m:
            inn_m = re.search(r'\b(\d{12})\b', flat_text)
        if not inn_m:
            inn_m = re.search(r'\b(\d{10})\b', flat_text)

        if inn_m:
            inn_val = inn_m.group(1).strip()
            bbox, page = find_field_bbox(inn_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="inn",
                    display_name="ИНН",
                    value=inn_val,
                    field_type="INN",
                    confidence=0.99,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. ФИО налогоплательщика
        fio_m = re.search(r'(?:физическому\s+лицу|гражданину|выдано|организации)\s*[:\.]?\s*([А-ЯЁ\s\-]{4,50}?)(?=\s*дата|\s*родив|\s*пол|\s*огрн|$)', flat_text, re.IGNORECASE)
        if fio_m:
            fio_val = fio_m.group(1).strip()
            words = fio_val.split()
            if len(words) in (2, 3, 4):
                bbox, page = find_field_bbox(words[0], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="taxpayer_name",
                        display_name="ФИО / Наименование налогоплательщика",
                        value=fio_val,
                        field_type="PERSON_NAME",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )

        # 3. Дата постановки на учёт
        date_m = re.search(r'(?:поставлен[ао]?\s*на\s*учет|дата\s*постановки|дата\s*выдачи)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if not date_m:
            date_m = re.search(r'(\d{2}[\.\/]\d{2}[\.\/](?:19\d{2}|20\d{2}))', flat_text)

        if date_m:
            dt = date_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(dt, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="registration_date",
                    display_name="Дата постановки на учёт",
                    value=dt,
                    field_type="DATE",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Налоговый орган (ИФНС)
        fns_m = re.search(r'((?:инспекция|межрайонная\s*инспекция)\s*федеральной\s*налоговой\s*службы\s*(?:№\s*\d+)?[А-Яа-я0-9\s\.\№\-]+?)(?=\s*код|\s*дата|\s*серия|$)', flat_text, re.IGNORECASE)
        if fns_m:
            fns_val = fns_m.group(1).strip()
            if len(fns_val) >= 10:
                bbox, page = find_field_bbox(fns_val[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="tax_authority",
                        display_name="Налоговый орган (ФНС)",
                        value=fns_val,
                        field_type="ORGANIZATION",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 5. Серия и номер бланка (например 77 № 012345678)
        blank_m = re.search(r'(?:серия\s*)?(\d{2}\s*(?:№|N)\s*\d{6,9})\b', flat_text, re.IGNORECASE)
        if blank_m:
            b_val = blank_m.group(1).strip()
            bbox, page = find_field_bbox(b_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="blank_series_number",
                    display_name="Серия и номер бланка",
                    value=b_val,
                    field_type="TEXT",
                    confidence=0.93,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. ОГРНИП / ОГРН (при наличии)
        ogrn_m = re.search(r'(?:огрнип|огрн)\s*[:\.]?\s*(\d{13}|\d{15})\b', flat_text, re.IGNORECASE)
        if ogrn_m:
            ogrn_val = ogrn_m.group(1)
            bbox, page = find_field_bbox(ogrn_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="ogrn",
                    display_name="ОГРН / ОГРНИП",
                    value=ogrn_val,
                    field_type="TEXT",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

        return fields

