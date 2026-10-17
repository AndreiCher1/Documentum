"""
Экстрактор реквизитов Акта сдачи-приемки выполненных работ / услуг (Act).

Извлекаемые ключевые поля:
- Номер акта
- Дата составления акта
- Основание (ссылка на договор)
- Заказчик и Исполнитель (наименования)
- ИНН Заказчика и Исполнителя
- Общая стоимость выполненных работ / оказанных услуг
- Сумма НДС
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


MONTH_MAP = {
    'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
    'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
    'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
}


class ActExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из актов выполненных работ."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Номер акта
        num_m = re.search(r'акт(?:\s+[а-яё\-]+)?\s*(?:№|N|No|#)\s*([A-Za-zА-Яа-я0-9\-\/]+)', flat_text, re.IGNORECASE)
        if num_m:
            a_num = num_m.group(1).strip()
            bbox, page = find_field_bbox(a_num, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="act_number",
                    display_name="Номер акта",
                    value=a_num,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. Дата акта (числовой и словесный формат)
        date_m = re.search(r'(?:от|дата)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        a_date = None
        raw_date_token = None

        if date_m:
            a_date = date_m.group(1).replace('/', '.')
            raw_date_token = date_m.group(1)
        else:
            verb_date_m = re.search(r'[«"]?(\d{1,2})[»"]?\s+([а-яё]+)\s+(\d{4})\s*г\.?', flat_text, re.IGNORECASE)
            if verb_date_m:
                d = int(verb_date_m.group(1))
                m_str = verb_date_m.group(2).lower()
                y = verb_date_m.group(3)
                if m_str in MONTH_MAP:
                    a_date = f"{d:02d}.{MONTH_MAP[m_str]}.{y}"
                    raw_date_token = verb_date_m.group(0)

        if a_date:
            bbox, page = find_field_bbox(raw_date_token or a_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="act_date",
                    display_name="Дата акта",
                    value=a_date,
                    field_type="DATE",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Ссылка на договор-основание
        contract_ref_m = re.search(r'(?:к\s*договору|по\s*договору|основание)\s*[:\s]*(?:№|N|No|#)?\s*([A-Za-zА-Яа-я0-9\-\/]+(?:\s*от\s*\d{2}\.\d{2}\.\d{4})?)', flat_text, re.IGNORECASE)
        if contract_ref_m:
            ref_val = contract_ref_m.group(1).strip()
            bbox, page = find_field_bbox(ref_val[:15], ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="contract_reference",
                    display_name="Основание (договор)",
                    value=ref_val,
                    field_type="TEXT",
                    confidence=0.91,
                    bbox=bbox,
                    page=page
                )
            )

        # 4. Заказчик и Исполнитель
        cust_m = re.search(r'заказчик\s*[:\.]?\s*([«"А-Яа-яA-Za-z0-9\s\.\-]+?)(?=\s*инн|\s*исполнитель|\s*подрядчик|$)', flat_text, re.IGNORECASE)
        if cust_m:
            c_name = cust_m.group(1).strip()
            if 3 <= len(c_name) <= 80:
                bbox, page = find_field_bbox(c_name[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="customer",
                        display_name="Заказчик",
                        value=c_name,
                        field_type="ORGANIZATION",
                        confidence=0.90,
                        bbox=bbox,
                        page=page
                    )
                )

        contr_m = re.search(r'исполнитель\s*[:\.]?\s*([«"А-Яа-яA-Za-z0-9\s\.\-]+?)(?=\s*инн|\s*заказчик|$)', flat_text, re.IGNORECASE)
        if contr_m:
            contr_name = contr_m.group(1).strip()
            if 3 <= len(contr_name) <= 80:
                bbox, page = find_field_bbox(contr_name[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="contractor",
                        display_name="Исполнитель",
                        value=contr_name,
                        field_type="ORGANIZATION",
                        confidence=0.90,
                        bbox=bbox,
                        page=page
                    )
                )

        # 5. ИНН сторон
        inns = list(re.finditer(r'\bинн\s*[:\.]?\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE))
        if inns:
            fields.append(
                ExtractedFieldValue(
                    name="contractor_inn",
                    display_name="ИНН исполнителя",
                    value=inns[0].group(1),
                    field_type="INN",
                    confidence=0.96,
                    bbox=find_field_bbox(inns[0].group(1), ocr_blocks)[0],
                    page=1
                )
            )
            if len(inns) >= 2:
                fields.append(
                    ExtractedFieldValue(
                        name="customer_inn",
                        display_name="ИНН заказчика",
                        value=inns[1].group(1),
                        field_type="INN",
                        confidence=0.96,
                        bbox=find_field_bbox(inns[1].group(1), ocr_blocks)[0],
                        page=1
                    )
                )

        # 6. Итоговая сумма работ
        sum_m = re.search(
            r'(?:всего\s*(?:оказано\s*услуг|выполнено\s*работ|работ|услуг)?\s*(?:на\s*сумму)?|итого|стоимость\s*работ)\s*[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
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
                        display_name="Сумма работ",
                        value=f"{amt_f:,.2f} руб.".replace(',', ' '),
                        field_type="AMOUNT",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 7. НДС
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
                    confidence=0.90,
                    bbox=bbox,
                    page=page
                )
            )

        return fields
