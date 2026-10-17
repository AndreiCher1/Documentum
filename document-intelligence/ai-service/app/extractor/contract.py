"""
Экстрактор реквизитов Договора (Contract / Agreement).

Извлекаемые ключевые поля:
- Номер договора
- Дата заключения договора (числовой и словесный формат)
- Город / место заключения
- Предмет или вид договора (поставки, оказания услуг, подряда, аренды, купли-продажи)
- Стороны договора (Сторона 1 / Заказчик, Сторона 2 / Исполнитель)
- ИНН сторон
- Сумма договора
- НДС
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


MONTH_MAP = {
    'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
    'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
    'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
}


class ContractExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из договоров."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Номер договора
        num_m = re.search(r'договор(?:\s+[а-яё\-]+)?\s*(?:№|N|No|#)\s*([A-Za-zА-Яа-я0-9\-\/]+)', flat_text, re.IGNORECASE)
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

        # 2. Дата договора
        date_m = re.search(r'(?:от|дата)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        c_date = None
        raw_date_token = None

        if date_m:
            c_date = date_m.group(1).replace('/', '.')
            raw_date_token = date_m.group(1)
        else:
            verb_date_m = re.search(r'[«"]?(\d{1,2})[»"]?\s+([а-яё]+)\s+(\d{4})\s*г\.?', flat_text, re.IGNORECASE)
            if verb_date_m:
                d = int(verb_date_m.group(1))
                m_str = verb_date_m.group(2).lower()
                y = verb_date_m.group(3)
                if m_str in MONTH_MAP:
                    c_date = f"{d:02d}.{MONTH_MAP[m_str]}.{y}"
                    raw_date_token = verb_date_m.group(0)

        if c_date:
            bbox, page = find_field_bbox(raw_date_token or c_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="contract_date",
                    display_name="Дата договора",
                    value=c_date,
                    field_type="DATE",
                    confidence=0.95,
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
                    display_name="Город заключения",
                    value=city_val,
                    field_type="TEXT",
                    confidence=0.91,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Вид договора
        kind_m = re.search(r'договор\s+(возмездного\s+оказания\s+услуг|купли-продажи|подряда|аренды|поставки|оказания\s+услуг)', flat_text, re.IGNORECASE)
        if kind_m:
            k_val = f"Договор {kind_m.group(1).lower()}"
            fields.append(
                ExtractedFieldValue(
                    name="contract_type",
                    display_name="Вид договора",
                    value=k_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=[0, 0, 0, 0],
                    page=1
                )
            )

        # 5. Стороны договора
        party1_m = re.search(r'(?:заказчик|покупатель|арендатор)\s*[:\-\s]\s*([«"А-Яа-я0-9\s\.\-]+?(?=,|именуем|\.|$))', flat_text, re.IGNORECASE)
        if party1_m:
            val1 = party1_m.group(1).strip()
            if 3 <= len(val1) <= 90:
                bbox, page = find_field_bbox(val1[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="customer",
                        display_name="Заказчик / Покупатель",
                        value=val1,
                        field_type="ORGANIZATION",
                        confidence=0.90,
                        bbox=bbox,
                        page=page
                    )
                )

        party2_m = re.search(r'(?:исполнитель|поставщик|подрядчик|арендодатель)\s*[:\-\s]\s*([«"А-Яа-я0-9\s\.\-]+?(?=,|именуем|\.|$))', flat_text, re.IGNORECASE)
        if party2_m:
            val2 = party2_m.group(1).strip()
            if 3 <= len(val2) <= 90:
                bbox, page = find_field_bbox(val2[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="contractor",
                        display_name="Исполнитель / Поставщик",
                        value=val2,
                        field_type="ORGANIZATION",
                        confidence=0.90,
                        bbox=bbox,
                        page=page
                    )
                )

        # 6. Сумма договора
        amount_m = re.search(
            r'(?:цена\s*договора|стоимость\s*договора|общая\s*стоимость|сумма\s*договора)\s*(?:составляет)?\s*[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
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
                        display_name="Сумма договора",
                        value=formatted_amt,
                        field_type="AMOUNT",
                        confidence=0.93,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 7. ИНН сторон
        inns = list(re.finditer(r'\bинн\s*[:\.]?\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE))
        if inns:
            first_inn = inns[0].group(1)
            bbox, page = find_field_bbox(first_inn, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="inn_party_1",
                    display_name="ИНН стороны 1",
                    value=first_inn,
                    field_type="INN",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )
            if len(inns) >= 2:
                second_inn = inns[1].group(1)
                bbox2, page2 = find_field_bbox(second_inn, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="inn_party_2",
                        display_name="ИНН стороны 2",
                        value=second_inn,
                        field_type="INN",
                        confidence=0.96,
                        bbox=bbox2,
                        page=page2
                    )
                )

        return fields
