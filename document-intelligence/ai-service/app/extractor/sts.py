"""
Экстрактор реквизитов Свидетельства о регистрации транспортного средства (СТС).

Извлекаемые ключевые поля:
- Государственный регистрационный знак (госномер)
- Идентификационный номер (VIN)
- Марка, модель ТС
- Тип ТС
- Категория ТС (A, B, C, D)
- Год выпуска
- Номер кузова / шасси
- Цвет кузова
- Мощность двигателя (л.с. / кВт)
- Разрешенная max масса / масса без нагрузки
- Собственник (ФИО / Наименование)
- Адрес регистрации собственника
- Номер бланка СТС
- Дата выдачи и подразделение ГИБДД
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


class StsExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из СТС."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Регистрационный знак (ГОСТ: 1 буква, 3 цифры, 2 буквы, 2-3 цифры региона)
        plate_m = re.search(r'\b([АВЕКМНОРСТУХA-Z]{1}\s*\d{3}\s*[АВЕКМНОРСТУХA-Z]{2}\s*\d{2,3})\b', flat_text, re.IGNORECASE)
        if plate_m:
            plate_val = re.sub(r'\s+', '', plate_m.group(1)).upper()
            bbox, page = find_field_bbox(plate_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="plate_number",
                    display_name="Государственный регистрационный знак",
                    value=plate_val,
                    field_type="TEXT",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. VIN номер (17 символов)
        vin_m = re.search(r'(?:vin|идентификационный\s*номер)\s*[:\.]?\s*([A-HJ-NPR-Z0-9]{17})\b', flat_text, re.IGNORECASE)
        if not vin_m:
            vin_m = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', flat_text)

        if vin_m:
            vin_val = vin_m.group(1).upper()
            bbox, page = find_field_bbox(vin_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="vin",
                    display_name="Идентификационный номер (VIN)",
                    value=vin_val,
                    field_type="VIN",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. Марка, модель ТС
        model_m = re.search(r'(?:марка,?\s*модель(?:\s*тс)?|марка)\s*[:\.]?\s*([A-Za-zА-Яа-я0-9\s\-]+?)(?=\s*тип\s*тс|\s*категория|\s*год\s*выпуска|$)', flat_text, re.IGNORECASE)
        if model_m:
            model_val = model_m.group(1).strip()
            if len(model_val) >= 2 and not model_val.isdigit():
                bbox, page = find_field_bbox(model_val[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="vehicle_model",
                        display_name="Марка, модель ТС",
                        value=model_val,
                        field_type="TEXT",
                        confidence=0.93,
                        bbox=bbox,
                        page=page
                    )
                )

        # 4. Категория ТС (A, B, C, D)
        cat_m = re.search(r'категория(?:\s*тс)?\s*[:\.]?\s*([A-Da-dА-Ва-в])\b', flat_text, re.IGNORECASE)
        if cat_m:
            cat_val = cat_m.group(1).upper()
            cat_map = {"А": "A", "В": "B", "С": "C", "D": "D"}
            cat_val = cat_map.get(cat_val, cat_val)
            bbox, page = find_field_bbox(cat_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="vehicle_category",
                    display_name="Категория ТС",
                    value=cat_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 5. Год выпуска
        year_m = re.search(r'год\s*выпуска(?:\s*тс)?\s*[:\.]?\s*((?:19\d{2}|20\d{2}))\b', flat_text, re.IGNORECASE)
        if year_m:
            y_val = year_m.group(1)
            bbox, page = find_field_bbox(y_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="manufacture_year",
                    display_name="Год выпуска ТС",
                    value=y_val,
                    field_type="YEAR",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. Номер кузова
        body_m = re.search(r'кузов\s*\(кабина\)?\s*[:\.]?\s*([A-Za-z0-9\-]+)', flat_text, re.IGNORECASE)
        if body_m:
            body_val = body_m.group(1).strip().upper()
            bbox, page = find_field_bbox(body_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="body_number",
                    display_name="Кузов (кабина) №",
                    value=body_val,
                    field_type="TEXT",
                    confidence=0.92,
                    bbox=bbox,
                    page=page
                )
            )

        # 7. Цвет
        color_m = re.search(r'цвет(?:\s*кузова)?\s*[:\.]?\s*([А-Яа-яA-Za-z\s\-]+?)(?=\s*мощность|\s*экологический|\s*паспорт|$)', flat_text, re.IGNORECASE)
        if color_m:
            color_val = color_m.group(1).strip()
            if len(color_val) >= 3 and not color_val.isdigit():
                bbox, page = find_field_bbox(color_val, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="color",
                        display_name="Цвет кузова",
                        value=color_val,
                        field_type="TEXT",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 8. Мощность двигателя (л.с. / кВт)
        power_m = re.search(r'мощность\s*двигателя\s*[:\.]?\s*([\d\.,\s]+(?:\s*к[вw]т\s*\/)?\s*[\d\.,\s]+\s*(?:л\.?с\.?|квт|hp))', flat_text, re.IGNORECASE)
        if power_m:
            power_val = power_m.group(1).strip()
            bbox, page = find_field_bbox(power_val[:10], ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="engine_power",
                    display_name="Мощность двигателя",
                    value=power_val,
                    field_type="TEXT",
                    confidence=0.92,
                    bbox=bbox,
                    page=page
                )
            )

        # 9. Разрешенная max масса
        mass_max_m = re.search(r'разрешенная\s*(?:m[аa]x|максимальная)?\s*масса(?:\s*,\s*кг)?\s*[:\.]?\s*(\d{3,6})', flat_text, re.IGNORECASE)
        if mass_max_m:
            mass_val = f"{mass_max_m.group(1)} кг"
            bbox, page = find_field_bbox(mass_max_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="max_weight",
                    display_name="Разрешенная max масса",
                    value=mass_val,
                    field_type="TEXT",
                    confidence=0.93,
                    bbox=bbox,
                    page=page
                )
            )

        # 10. Серия и номер бланка СТС (2 цифры + 2 буквы/цифры + 6 цифр)
        sts_num_m = re.search(r'\b(\d{2}\s*[А-Яа-яA-Za-z0-9]{2}\s*\d{6})\b', flat_text)
        if sts_num_m:
            sts_num_val = sts_num_m.group(1).strip()
            bbox, page = find_field_bbox(sts_num_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="sts_number",
                    display_name="Серия и номер СТС",
                    value=sts_num_val,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 11. Собственник (ФИО)
        owner_m = re.search(r'собственник\s*[:\.]?\s*([А-ЯЁ\s\-]{4,40}?)(?=\s*республика|\s*край|\s*область|\s*г\.|\s*район|\s*ул\.|$)', flat_text, re.IGNORECASE)
        if owner_m:
            owner_val = owner_m.group(1).strip()
            if len(owner_val.split()) >= 2:
                bbox, page = find_field_bbox(owner_val.split()[0], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="owner_name",
                        display_name="Собственник ТС",
                        value=owner_val,
                        field_type="PERSON_NAME",
                        confidence=0.91,
                        bbox=bbox,
                        page=page
                    )
                )

        return fields
