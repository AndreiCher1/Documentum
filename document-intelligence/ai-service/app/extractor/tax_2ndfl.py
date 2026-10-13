"""
Экстрактор реквизитов Справки о доходах физического лица (2-НДФЛ).

Извлекаемые ключевые поля:
- Отчётный налоговый год
- Налоговый агент (наименование работодателя)
- ИНН/КПП работодателя
- ФИО налогоплательщика (получателя дохода)
- ИНН налогоплательщика
- Ставка налога (13% / 15%)
- Общая сумма дохода
- Налоговая база
- Сумма налога исчисленная и удержанная
"""

import re
from typing import Any, List, Optional

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class Tax2NdflExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из справок 2-НДФЛ."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Отчётный год (за 20XX год)
        year_m = re.search(r'(?:за|налоговый\s*период|отчетный\s*год)\s*[:\s]*((?:20)\d{2})\s*(?:год|г\.)?', flat_text, re.IGNORECASE)
        if year_m:
            yr = year_m.group(1)
            bbox, page = find_field_bbox(yr, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="tax_year",
                    display_name="Отчётный год",
                    value=yr,
                    field_type="NUMBER",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. ИНН налогового агента / физлица
        inns = list(re.finditer(r'\bинн\s*[:\.]?\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE))
        if inns:
            # Первый ИНН — обычно работодатель (10 цифр юрлицо)
            agent_inn = inns[0].group(1)
            bbox, page = find_field_bbox(agent_inn, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="agent_inn",
                    display_name="ИНН налогового агента",
                    value=agent_inn,
                    field_type="INN",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

            # Второй ИНН (если есть) — физлицо (обычно 12 цифр)
            if len(inns) >= 2:
                person_inn = inns[1].group(1)
                bbox2, page2 = find_field_bbox(person_inn, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="taxpayer_inn",
                        display_name="ИНН получателя",
                        value=person_inn,
                        field_type="INN",
                        confidence=0.97,
                        bbox=bbox2,
                        page=page2
                    )
                )

        # 3. Ставка налога (13% / 15%)
        rate_m = re.search(r'(?:ставка\s*налога|ставка)\s*[:\s]*(\d{1,2})\s*%', flat_text, re.IGNORECASE)
        if rate_m:
            rate_val = f"{rate_m.group(1)}%"
            bbox, page = find_field_bbox(rate_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="tax_rate",
                    display_name="Ставка налога",
                    value=rate_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Общая сумма дохода
        income_m = re.search(
            r'(?:общая\s*сумма\s*дохода|сумма\s*дохода)\s*[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
            flat_text,
            re.IGNORECASE
        )
        if income_m:
            raw_inc = income_m.group(1).strip()
            clean_inc = re.sub(r'\s+', '', raw_inc).replace(',', '.')
            try:
                inc_f = float(clean_inc)
                bbox, page = find_field_bbox(raw_inc, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="total_income",
                        display_name="Общая сумма дохода",
                        value=f"{inc_f:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 5. Сумма налога исчисленная / удержанная
        tax_m = re.search(
            r'(?:сумма\s*налога\s*исчисленная|сумма\s*налога\s*удержанная|налог\s*удержанный)\s*[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
            flat_text,
            re.IGNORECASE
        )
        if tax_m:
            raw_tax = tax_m.group(1).strip()
            clean_tax = re.sub(r'\s+', '', raw_tax).replace(',', '.')
            try:
                tax_f = float(clean_tax)
                bbox, page = find_field_bbox(raw_tax, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="tax_withheld",
                        display_name="Налог удержанный",
                        value=f"{tax_f:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        return fields

