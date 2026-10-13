"""
Экстрактор реквизитов Договора (Contract / Agreement).

Извлекаемые ключевые поля:
- Номер договора
- Дата заключения договора
- Город / место заключения
- Предмет или вид договора (поставки, оказания услуг, подряда)
- Стороны договора (Заказчик, Исполнитель, Поставщик)
- Сумма договора
"""

import re
from typing import Any, List, Optional

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class ContractExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из договоров."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Номер договора
        num_m = re.search(r'договор(?:\s+[а-яё]+)?\s*(?:№|N|No|#)\s*([A-Za-zА-Яа-я0-9\-\/]+)', flat_text, re.IGNORECASE)
        if num_m:
            c_num = num_m.group(1).strip()
            bbox, page = find_field_bbox(c_num, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="contract_number",
                    display_name="Номер договора",
                    value=c_num,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. Дата договора (цифровой или словесный формат)
        # Пример: "от 15.01.2024" или "«15» января 2024"
        date_m = re.search(r'(?:от|дата)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if not date_m:
            date_m = re.search(r'([«"]?\d{1,2}[»"]?\s+[а-яё]+\s+\d{4}\s*г\.?)', flat_text, re.IGNORECASE)

        if date_m:
            c_date = date_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(c_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="contract_date",
                    display_name="Дата договора",
                    value=c_date,
                    field_type="DATE",
                    confidence=0.94,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Город заключения
        city_m = re.search(r'\bг\.\s*([А-Яа-я\-]+)\b', flat_text)
        if city_m:
            city_val = f"г. {city_m.group(1)}"
            bbox, page = find_field_bbox(city_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="city",
                    display_name="Город",
                    value=city_val,
                    field_type="TEXT",
                    confidence=0.90,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Стороны договора
        # Поиск Заказчика / Исполнителя / Поставщика
        party_customer = re.search(r'(?:заказчик|покупатель|арендатор)\s*[:\-\s]\s*([«"А-Яа-я0-9\s]+?(?=,|именуем|\.|$))', flat_text, re.IGNORECASE)
        if party_customer:
            val_cust = party_customer.group(1).strip()
            if len(val_cust) >= 3 and len(val_cust) <= 80:
                bbox, page = find_field_bbox(val_cust[:20], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="customer",
                        display_name="Заказчик / Покупатель",
                        value=val_cust,
                        field_type="ORGANIZATION",
                        confidence=0.88,
                        bbox=bbox,
                        page=page
                    )
                )

        party_contractor = re.search(r'(?:исполнитель|поставщик|арендодатель|подрядчик)\s*[:\-\s]\s*([«"А-Яа-я0-9\s]+?(?=,|именуем|\.|$))', flat_text, re.IGNORECASE)
        if party_contractor:
            val_contr = party_contractor.group(1).strip()
            if len(val_contr) >= 3 and len(val_contr) <= 80:
                bbox, page = find_field_bbox(val_contr[:20], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="contractor",
                        display_name="Исполнитель / Поставщик",
                        value=val_contr,
                        field_type="ORGANIZATION",
                        confidence=0.88,
                        bbox=bbox,
                        page=page
                    )
                )

        # 5. Сумма договора
        sum_m = re.search(
            r'(?:сумма\s*договора|цена\s*договора|стоимость\s*работ|стоимость\s*услуг|составляет)\s*[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)',
            flat_text,
            re.IGNORECASE
        )
        if sum_m:
            raw_s = sum_m.group(1).strip()
            clean_s = re.sub(r'\s+', '', raw_s).replace(',', '.')
            try:
                amt_f = float(clean_s)
                bbox, page = find_field_bbox(raw_s, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="total_amount",
                        display_name="Сумма договора",
                        value=f"{amt_f:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        return fields

