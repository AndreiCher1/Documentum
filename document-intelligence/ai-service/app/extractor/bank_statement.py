"""
Экстрактор реквизитов Банковской выписки (Bank Statement).

Извлекаемые ключевые поля:
- Наименование банка
- БИК банка
- Номер расчётного счёта клиента (20 цифр)
- Период выписки
- Входящий остаток
- Исходящий остаток
- Оборот по дебету (списания)
- Оборот по кредиту (поступления)
- Владелец счёта (клиент)
- Валюта счёта
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class BankStatementExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из банковских выписок."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Расчётный счёт клиента (20 цифр)
        acc_m = re.search(r'(?:расчетный\s*счет|р\/с|счет\s*клиента|номер\s*счета)\s*[:\.]?\s*(\d{20})\b', flat_text, re.IGNORECASE)
        if not acc_m:
            acc_m = re.search(r'\b(40702\d{15}|40817\d{15}|40802\d{15}|40502\d{15})\b', flat_text)

        if acc_m:
            acc_val = acc_m.group(1)
            bbox, page = find_field_bbox(acc_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="account_number",
                    display_name="Расчётный счёт",
                    value=acc_val,
                    field_type="ACCOUNT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. БИК банка (9 цифр, начинается с 04)
        bik_m = re.search(r'\bбик\s*[:\.]?\s*(04\d{7})\b', flat_text, re.IGNORECASE)
        if bik_m:
            bik_val = bik_m.group(1)
            bbox, page = find_field_bbox(bik_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="bik",
                    display_name="БИК банка",
                    value=bik_val,
                    field_type="BIK",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Период выписки (например "за период с 01.01.2024 по 31.01.2024")
        period_m = re.search(r'(?:период|за\s*период)?\s*(?:с\s*)?(\d{2}[\.\/]\d{2}[\.\/]\d{4})\s*(?:по|-|—)\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if period_m:
            d_from = period_m.group(1).replace('/', '.')
            d_to = period_m.group(2).replace('/', '.')
            p_val = f"с {d_from} по {d_to}"
            bbox, page = find_field_bbox(d_from, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="statement_period",
                    display_name="Период выписки",
                    value=p_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Входящий остаток
        in_m = re.search(r'(?:входящий\s*остаток|сальдо\s*входящее|остаток\s*на\s*начало)\s*[:\.]?\s*([\d\s]+(?:[\.,]\d{2})?)\b', flat_text, re.IGNORECASE)
        if in_m:
            raw_s = in_m.group(1).strip()
            clean_s = re.sub(r'\s+', '', raw_s).replace(',', '.')
            try:
                amt = float(clean_s)
                bbox, page = find_field_bbox(raw_s, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="opening_balance",
                        display_name="Входящий остаток",
                        value=f"{amt:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 5. Исходящий остаток
        out_m = re.search(r'(?:исходящий\s*остаток|сальдо\s*исходящее|остаток\s*на\s*конец)\s*[:\.]?\s*([\d\s]+(?:[\.,]\d{2})?)\b', flat_text, re.IGNORECASE)
        if out_m:
            raw_s = out_m.group(1).strip()
            clean_s = re.sub(r'\s+', '', raw_s).replace(',', '.')
            try:
                amt = float(clean_s)
                bbox, page = find_field_bbox(raw_s, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="closing_balance",
                        display_name="Исходящий остаток",
                        value=f"{amt:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 6. Оборот по дебету (списания)
        deb_m = re.search(r'(?:оборот\s*по\s*дебету|дебет|всего\s*списано)\s*[:\.]?\s*([\d\s]+(?:[\.,]\d{2})?)\b', flat_text, re.IGNORECASE)
        if deb_m:
            raw_s = deb_m.group(1).strip()
            clean_s = re.sub(r'\s+', '', raw_s).replace(',', '.')
            try:
                amt = float(clean_s)
                bbox, page = find_field_bbox(raw_s, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="debit_turnover",
                        display_name="Оборот по дебету (расход)",
                        value=f"{amt:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.93,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 7. Оборот по кредиту (поступления)
        cred_m = re.search(r'(?:оборот\s*по\s*кредиту|кредит|всего\s*поступило)\s*[:\.]?\s*([\d\s]+(?:[\.,]\d{2})?)\b', flat_text, re.IGNORECASE)
        if cred_m:
            raw_s = cred_m.group(1).strip()
            clean_s = re.sub(r'\s+', '', raw_s).replace(',', '.')
            try:
                amt = float(clean_s)
                bbox, page = find_field_bbox(raw_s, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="credit_turnover",
                        display_name="Оборот по кредиту (приход)",
                        value=f"{amt:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.93,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 8. Наименование банка
        bank_m = re.search(r'(?:пао|ао|банк)\s*[«"А-Яа-яA-Za-z0-9\s\-]+(?:\s*банк)?', flat_text, re.IGNORECASE)
        if bank_m:
            bank_name = bank_m.group(0).strip()
            if len(bank_name) <= 50 and any(k in bank_name.lower() for k in ["банк", "сбер", "втб", "тинькофф", "альфа"]):
                bbox, page = find_field_bbox(bank_name[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="bank_name",
                        display_name="Наименование банка",
                        value=bank_name,
                        field_type="ORGANIZATION",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        return fields
