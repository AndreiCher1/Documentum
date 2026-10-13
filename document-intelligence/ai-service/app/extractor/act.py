"""
Экстрактор реквизитов Акта сдачи-приемки выполненных работ / услуг (Act).

Извлекаемые ключевые поля:
- Номер акта
- Дата составления акта
- Основание (ссылка на договор)
- Заказчик и Исполнитель
- Общая стоимость выполненных работ / оказанных услуг
- Сумма НДС
"""

import re
from typing import Any, List, Optional

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


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

        # 2. Дата акта
        date_m = re.search(r'(?:от|дата)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if date_m:
            a_date = date_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(a_date, ocr_blocks)
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
        contract_ref_m = re.search(r'(?:к\s*договору|по\s*договору)\s*(?:№|N|No|#)?\s*([A-Za-zА-Яа-я0-9\-\/]+(?:\s*от\s*\d{2}\.\d{2}\.\d{4})?)', flat_text, re.IGNORECASE)
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

        # 4. Итоговая сумма работ
        sum_m = re.search(
            r'(?:всего\s*(?:работ|услуг)?\s*(?:на\s*сумму)?|итого|стоимость\s*работ)\s*[:\s]*([\d\s]+(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
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

        # 5. НДС
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

