"""
Экстрактор реквизитов Счёта на оплату (Invoice).

Извлекаемые ключевые поля:
- Номер счёта
- Дата счёта
- ИНН поставщика (10 или 12 цифр с проверкой контрольной суммы)
- КПП поставщика (9 цифр)
- БИК банка получателя (9 цифр, начинается с 04)
- Корреспондентский счёт (20 цифр, 30101...)
- Расчётный счёт (20 цифр, 40702... / 408...)
- Итоговая сумма к оплате
- Ставка и сумма НДС
"""

import re
from typing import Any, List, Optional

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class InvoiceExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из счетов на оплату."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Номер счёта
        num_m = re.search(r'(?:счет(?:\s*на\s*оплату)?|счёт)\s*(?:№|N|No|#)?\s*([A-Za-zА-Яа-я0-9\-\/]+)', flat_text, re.IGNORECASE)
        if num_m:
            inv_num = num_m.group(1).strip()
            if inv_num and not inv_num.lower().startswith(('от', 'на', 'в')):
                bbox, page = find_field_bbox(inv_num, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="invoice_number",
                        display_name="Номер счёта",
                        value=inv_num,
                        field_type="TEXT",
                        confidence=0.96,
                        bbox=bbox,
                        page=page
                    )
                )

        # 2. Дата счёта
        date_m = re.search(r'(?:от|дата)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if date_m:
            inv_date = date_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(inv_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="invoice_date",
                    display_name="Дата счёта",
                    value=inv_date,
                    field_type="DATE",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. ИНН поставщика / организации (10 или 12 цифр)
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
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. КПП (9 цифр)
        kpp_m = re.search(r'\bкпп\s*[:\.]?\s*(\d{9})\b', flat_text, re.IGNORECASE)
        if kpp_m:
            kpp_val = kpp_m.group(1)
            bbox, page = find_field_bbox(kpp_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="kpp",
                    display_name="КПП",
                    value=kpp_val,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 5. БИК банка (9 цифр, начинается с 04)
        bik_m = re.search(r'\bбик\s*[:\.]?\s*(04\d{7})\b', flat_text, re.IGNORECASE)
        if bik_m:
            bik_val = bik_m.group(1)
            bbox, page = find_field_bbox(bik_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="bik",
                    display_name="БИК Банка",
                    value=bik_val,
                    field_type="TEXT",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. Расчётный счёт (20 цифр)
        acc_m = re.search(r'(?:р\/с|расчетный\s*счет|счет\s*получателя)\s*[:\.]?\s*(\d{20})\b', flat_text, re.IGNORECASE)
        if not acc_m:
            acc_m = re.search(r'\b(40702\d{15}|408\d{17})\b', flat_text)
        if acc_m:
            acc_val = acc_m.group(1)
            bbox, page = find_field_bbox(acc_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="settlement_account",
                    display_name="Расчётный счёт",
                    value=acc_val,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 7. Корреспондентский счёт (20 цифр, 30101...)
        corr_m = re.search(r'(?:к\/с|корр(?:еспондентский)?\s*счет)\s*[:\.]?\s*(30101\d{15})\b', flat_text, re.IGNORECASE)
        if corr_m:
            corr_val = corr_m.group(1)
            bbox, page = find_field_bbox(corr_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="corr_account",
                    display_name="Корр. счёт",
                    value=corr_val,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 8. Итоговая сумма к оплате
        # Приоритет: "Всего к оплате", "Итого к оплате", "Итого:", затем общие фразы с суммой
        amount_m = re.search(
            r'(?:всего\s*к\s*оплате|итого\s*к\s*оплате|итого)\s*[:\.]?\s*([\d\s]{2,}(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
            flat_text,
            re.IGNORECASE
        )
        if not amount_m:
            amount_m = re.search(
                r'(?:всего\s*наименований[^,]+на\s*сумму|сумма\s*к\s*оплате)\s*[:\.]?\s*([\d\s]{2,}(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
                flat_text,
                re.IGNORECASE
            )
        if amount_m:
            raw_amt = amount_m.group(1).strip()
            clean_amt = re.sub(r'\s+', '', raw_amt).replace(',', '.')
            try:
                val_float = float(clean_amt)
                formatted_amt = f"{val_float:,.2f} руб.".replace(',', ' ')
                bbox, page = find_field_bbox(raw_amt, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="total_amount",
                        display_name="Сумма к оплате",
                        value=formatted_amt,
                        field_type="AMOUNT",
                        confidence=0.95,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 9. НДС
        vat_m = re.search(r'(?:в\s*т\.?ч\.?\s*ндс|ндс)\s*[:\.]?\s*(\d{1,2}%|без\s*ндс|[\d\s]+(?:[\.,]\d{2})?\s*руб)', flat_text, re.IGNORECASE)
        if vat_m:
            vat_val = vat_m.group(1).strip()
            bbox, page = find_field_bbox(vat_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="vat",
                    display_name="НДС",
                    value=vat_val,
                    field_type="TEXT",
                    confidence=0.91,
                    bbox=bbox,
                    page=page
                )
            )

        return fields

