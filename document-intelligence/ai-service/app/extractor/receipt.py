"""
Экстрактор реквизитов квитанций ЖКУ и счетов за коммунальные услуги.

Извлекаемые ключевые поля:
- Итого к оплате (руб.)
- Начислено за период (руб.)
- Тариф / Цена
- Объем потребления (м3 / кВт / Гкал)
- Номер лицевого счета
- Долг (+) / Аванс (-)
- Оплачено ранее
- Дата / Расчетный период
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class ReceiptExtractor(BaseFieldExtractor):
    """Экстрактор реквизитов квитанций ЖКУ и коммунальных счетов."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(line.strip() for line in text.split('\n') if line.strip())

        # 1. Итого к оплате
        total_match = re.search(r'(?:итого\s+к\s+оплате|всего\s+к\s+оплате|к\s+оплате)[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?', flat_text, re.IGNORECASE)
        if total_match:
            raw_val = total_match.group(1).strip()
            clean_val = re.sub(r'\s+', '', raw_val)
            bbox, page = find_field_bbox(raw_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="total_amount",
                    display_name="Итого к оплате",
                    value=f"{raw_val} руб.",
                    field_type="AMOUNT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. Начислено за период
        accrued_match = re.search(r'начислено[,:\s]*руб\.?[:\s]*([\d\s]+(?:[\.,]\d{2})?)', flat_text, re.IGNORECASE)
        if accrued_match:
            raw_val = accrued_match.group(1).strip()
            bbox, page = find_field_bbox(raw_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="accrued_amount",
                    display_name="Начислено за период",
                    value=f"{raw_val} руб.",
                    field_type="AMOUNT",
                    confidence=0.94,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Объем потребления
        vol_match = re.search(r'(?:объем|объ[её]м)[,\s]*м3[:\s]*([\d\s]+(?:[\.,]\d{1,4})?)', flat_text, re.IGNORECASE)
        if vol_match:
            raw_val = vol_match.group(1).strip()
            bbox, page = find_field_bbox(raw_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="consumption_volume",
                    display_name="Объём потребления",
                    value=f"{raw_val} м3",
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Цена / Тариф
        price_match = re.search(r'(?:цена|тариф)[,\s]*руб\.?[:\s]*([\d\s]+(?:[\.,]\d{2})?)', flat_text, re.IGNORECASE)
        if price_match:
            raw_val = price_match.group(1).strip()
            bbox, page = find_field_bbox(raw_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="tariff_rate",
                    display_name="Тариф / Цена",
                    value=f"{raw_val} руб.",
                    field_type="AMOUNT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 5. Лицевой счёт
        acc_match = re.search(r'(?:лицев(?:ой|ого)\s+сч[её]т\w*|л[\/\.]?\s*сч?\s*№?|\bл\/с\b)[:\s]*([A-Za-z0-9\-\s]{6,20})', flat_text, re.IGNORECASE)
        if acc_match:
            raw_val = acc_match.group(1).strip()
            clean_acc = re.sub(r'\s+', '', raw_val)
            bbox, page = find_field_bbox(clean_acc, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="account_number",
                    display_name="Лицевой счёт",
                    value=clean_acc,
                    field_type="TEXT",
                    confidence=0.92,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. Дата / Расчетный период
        date_match = re.search(r'(?:на|за|период)[:\s]*([0-3]?\d[\./][0-1]?\d[\./](?:20)?\d{2})', flat_text, re.IGNORECASE)
        if date_match:
            raw_date = date_match.group(1).strip().replace('/', '.')
            bbox, page = find_field_bbox(raw_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="period_date",
                    display_name="Расчётный период",
                    value=raw_date,
                    field_type="DATE",
                    confidence=0.94,
                    bbox=bbox,
                    page=page
                )
            )

        return fields

