"""
Универсальный экстрактор общих реквизитов (Generic Extractor).

Используется для неклассифицированных документов (UNKNOWN) или как дополнение:
- Календарные даты
- ИНН (10 и 12 цифр)
- Денежные суммы
- Номера телефонов
- Email-адреса
"""

import re
from typing import Any, List, Optional

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class GenericFieldExtractor(BaseFieldExtractor):
    """Экстрактор базовых реквизитов общего назначения."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Даты
        date_pattern = r'\b(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.(19\d\d|20\d\d)\b'
        dates = list(re.finditer(date_pattern, flat_text))
        for idx, d_match in enumerate(dates[:3], start=1):
            d_val = d_match.group(0)
            bbox, page = find_field_bbox(d_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name=f"date_{idx}",
                    display_name=f"Дата {idx}",
                    value=d_val,
                    field_type="DATE",
                    confidence=0.88,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. ИНН
        inn_m = re.search(r'\bинн\s*[:\.]?\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE)
        if inn_m:
            inn_val = inn_m.group(1)
            bbox, page = find_field_bbox(inn_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="inn",
                    display_name="ИНН",
                    value=inn_val,
                    field_type="INN",
                    confidence=0.92,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Email
        email_m = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', flat_text)
        if email_m:
            email_val = email_m.group(0)
            bbox, page = find_field_bbox(email_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="email",
                    display_name="Email",
                    value=email_val,
                    field_type="EMAIL",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Телефон
        phone_m = re.search(r'(?:\+7|8)\s*[\(\-]?\s*\d{3}\s*[\)\-]?\s*\d{3}[\-\s]?\d{2}[\-\s]?\d{2}', flat_text)
        if phone_m:
            phone_val = phone_m.group(0).strip()
            bbox, page = find_field_bbox(phone_val[:10], ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="phone",
                    display_name="Телефон",
                    value=phone_val,
                    field_type="PHONE",
                    confidence=0.90,
                    bbox=bbox,
                    page=page
                )
            )

        return fields

