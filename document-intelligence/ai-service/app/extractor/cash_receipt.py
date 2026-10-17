"""
Экстрактор реквизитов Кассового чека (54-ФЗ).

Извлекаемые ключевые поля:
- Итоговая сумма к оплате (ИТОГ / ПОЛУЧЕНО)
- Дата и время покупки
- Наименование продавца (ООО / ИП / Торговая точка)
- ИНН продавца (10 или 12 цифр)
- Способ оплаты (Безналичными / Наличными)
- Номер чека и смены
- Кассир
- Фискальный накопитель (ФН, 16 цифр)
- Номер фискального документа (ФД)
- Фискальный признак документа (ФП / ФПД)
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class CashReceiptExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из кассовых чеков."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Итоговая сумма (ИТОГ, ИТОГО, ВСЕГО, СУММА)
        total_m = re.search(r'(?:итог|итого|всего|сумма|к\s*оплате)\s*[:\=]?\s*([\d\s]+(?:[\.,]\d{2})?)\b', flat_text, re.IGNORECASE)
        if total_m:
            raw_s = total_m.group(1).strip()
            clean_s = re.sub(r'\s+', '', raw_s).replace(',', '.')
            try:
                amt = float(clean_s)
                bbox, page = find_field_bbox(raw_s, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="total_amount",
                        display_name="Итоговая сумма",
                        value=f"{amt:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.97,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 2. ИНН продавца (10 или 12 цифр)
        inn_m = re.search(r'\bинн\s*[:\.]?\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE)
        if inn_m:
            inn_val = inn_m.group(1)
            bbox, page = find_field_bbox(inn_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="seller_inn",
                    display_name="ИНН продавца",
                    value=inn_val,
                    field_type="INN",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Дата и время покупки
        dt_m = re.search(r'(\d{2}[\.\/]\d{2}[\.\/](?:20)?\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?)', flat_text)
        if not dt_m:
            dt_m = re.search(r'(\d{2}[\.\/]\d{2}[\.\/](?:20)?\d{2})', flat_text)

        if dt_m:
            dt_val = dt_m.group(1).strip()
            bbox, page = find_field_bbox(dt_val[:10], ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="receipt_datetime",
                    display_name="Дата и время чека",
                    value=dt_val,
                    field_type="DATE",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Способ оплаты
        if re.search(r'безналичн|электронн|карт|безнал', flat_text, re.IGNORECASE):
            pay_type = "Безналичный расчет"
        elif re.search(r'наличн', flat_text, re.IGNORECASE):
            pay_type = "Наличные"
        else:
            pay_type = "Не указан"

        fields.append(
            ExtractedFieldValue(
                name="payment_type",
                display_name="Способ оплаты",
                value=pay_type,
                field_type="TEXT",
                confidence=0.90,
                bbox=[0, 0, 0, 0],
                page=1
            )
        )

        # 5. Фискальный накопитель (ФН, 16 цифр)
        fn_m = re.search(r'(?:фн|номер\s*фн)\s*(?:№|N)?\s*(\d{16})\b', flat_text, re.IGNORECASE)
        if not fn_m:
            fn_m = re.search(r'\b(\d{16})\b', flat_text)
        if fn_m:
            fn_val = fn_m.group(1)
            bbox, page = find_field_bbox(fn_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="fn_number",
                    display_name="Номер ФН (фискальный накопитель)",
                    value=fn_val,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. Номер фискального документа (ФД)
        fd_m = re.search(r'(?:фд|номер\s*фд)\s*(?:№|N)?\s*(\d{1,10})\b', flat_text, re.IGNORECASE)
        if fd_m:
            fd_val = fd_m.group(1)
            bbox, page = find_field_bbox(fd_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="fd_number",
                    display_name="Номер документа (ФД)",
                    value=fd_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 7. Фискальный признак (ФП / ФПД)
        fpd_m = re.search(r'(?:фпд|фп)\s*(?:№|N)?\s*(\d{8,12})\b', flat_text, re.IGNORECASE)
        if fpd_m:
            fpd_val = fpd_m.group(1)
            bbox, page = find_field_bbox(fpd_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="fpd_number",
                    display_name="Фискальный признак (ФПД)",
                    value=fpd_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 8. Наименование продавца (первые строки)
        seller_m = re.search(r'(?:ооо|зао|пао|ао|ип)\s*[«"А-Яа-яA-Za-z0-9\s\.\-]+', flat_text, re.IGNORECASE)
        if seller_m:
            s_val = seller_m.group(0).strip()
            if len(s_val) <= 60:
                bbox, page = find_field_bbox(s_val[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="seller_name",
                        display_name="Наименование продавца",
                        value=s_val,
                        field_type="ORGANIZATION",
                        confidence=0.91,
                        bbox=bbox,
                        page=page
                    )
                )

        return fields
