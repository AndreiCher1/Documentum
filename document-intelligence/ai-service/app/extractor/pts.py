"""
Экстрактор реквизитов Паспорта транспортного средства (ПТС).

Извлекаемые ключевые поля:
- Серия и номер ПТС (например: 77 УО 817676)
- Идентификационный номер (VIN, 17 символов)
- Марка, модель ТС (например: BMW 118I)
- Тип ТС
- Категория ТС (A, B, C, D, прицеп)
- Год изготовления (4 цифры)
- Модель, № двигателя
- Кузов (кабина, прицеп) №
- Цвет кузова
- Мощность двигателя (л.с. / кВт)
- Рабочий объём двигателя (куб. см)
- Тип двигателя (БЕНЗИНОВЫЙ, ДИЗЕЛЬНЫЙ, ЭЛЕКТРИЧЕСКИЙ)
- Экологический класс (ПЯТЫЙ, ЧЕТВЕРТЫЙ, 5, 4 и т.д.)
- Разрешенная максимальная масса (кг)
- Масса без нагрузки (кг)
- Организация-изготовитель ТС (страна)
- Собственник ТС (ФИО / Наименование)
- Адрес собственника
- Орган, выдавший ПТС (Таможня / ГИБДД)
- Дата выдачи ПТС
"""

import re
from typing import Any, List, Optional
from app.extractor.base import (
    BaseFieldExtractor,
    ExtractedFieldValue,
    find_field_bbox,
    find_spatial_field,
    normalize_vin
)


class PtsExtractor(BaseFieldExtractor):
    """Экстрактор полей из Паспорта транспортного средства (ПТС)."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text and not ocr_blocks:
            return fields

        flat_text = " ".join(text.split()) if text else ""

        # 1. Серия и номер ПТС (формат: 2 цифры + 2 русские буквы + 6 цифр, например 77 УО 817676)
        series_m = re.search(r'\b(\d{2}\s*[А-Яа-яA-Za-z]{2}\s*\d{6})\b', flat_text)
        if series_m:
            s_val = series_m.group(1).strip()
            bbox, page = find_field_bbox(s_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="series_number",
                    display_name="Серия и номер ПТС",
                    value=s_val,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. VIN номер (17 символов с нормализацией O->0, Q->0, I->1)
        v_raw, v_bbox, v_page = find_spatial_field(
            r'идентификацион\w*\s*номер|(?:\b|\()vin(?:\b|\))',
            ocr_blocks,
            value_filter=lambda v: len(re.sub(r'[^A-Za-z0-9]', '', v)) >= 14
        )
        vin_norm = normalize_vin(v_raw) if v_raw else None
        if not vin_norm:
            for cand in re.findall(r'\b([A-Za-z0-9]{17})\b', flat_text):
                norm = normalize_vin(cand)
                if norm:
                    vin_norm = norm
                    v_bbox, v_page = find_field_bbox(cand, ocr_blocks)
                    break
        if vin_norm:
            fields.append(
                ExtractedFieldValue(
                    name="vin",
                    display_name="Идентификационный номер (VIN)",
                    value=vin_norm,
                    field_type="VIN",
                    confidence=0.98,
                    bbox=v_bbox,
                    page=v_page
                )
            )

        # 3. Марка, модель ТС
        m_val, m_bbox, m_page = find_spatial_field(
            r'2\.\s*марка,?\s*модель|марка,?\s*модель(?:\s*тс)?',
            ocr_blocks,
            value_filter=lambda v: len(v) >= 2 and not v.isdigit()
        )
        if not m_val:
            model_m = re.search(r'2\.\s*Марка,?\s*модель(?:\s*ТС)?\s*[:\.]?\s*([A-Za-zА-Яа-я0-9\s\-]+?)(?=\s*3\.|\s*Наименование|\s*Категория|$)', flat_text, re.IGNORECASE)
            if model_m:
                candidate = model_m.group(1).strip()
                if len(candidate) >= 2 and not candidate.isdigit():
                    m_val = candidate
                    m_bbox, m_page = find_field_bbox(candidate, ocr_blocks)

        if m_val:
            fields.append(
                ExtractedFieldValue(
                    name="vehicle_model",
                    display_name="Марка, модель ТС",
                    value=m_val.strip(),
                    field_type="TEXT",
                    confidence=0.94,
                    bbox=m_bbox,
                    page=m_page
                )
            )

        # 4. Категория ТС (A, B, C, D, прицеп)
        cat_m = re.search(r'4\.\s*Категория(?:\s*ТС)?\s*[:\.]?\s*([A-Da-dА-Ва-в])\b', flat_text, re.IGNORECASE)
        if cat_m:
            cat_val = cat_m.group(1).upper()
            bbox, page = find_field_bbox(cat_val, ocr_blocks)
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

        # 5. Год изготовления
        year_m = re.search(r'5\.\s*Год\s*изготовления(?:\s*ТС)?\s*[:\.]?\s*(19\d{2}|20\d{2})\b', flat_text, re.IGNORECASE)
        if year_m:
            year_val = year_m.group(1)
            bbox, page = find_field_bbox(year_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="manufacture_year",
                    display_name="Год изготовления",
                    value=year_val,
                    field_type="TEXT",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

        # 6. Мощность двигателя, л.с. (кВт)
        power_m = re.search(r'10\.\s*Мощность\s*двигателя[^\d]*(\d{2,4})\s*(?:л\.\s*с\.|\/|\(|\s+|$)', flat_text, re.IGNORECASE)
        if power_m:
            power_val = power_m.group(1).strip() + " л.с."
            bbox, page = find_field_bbox(power_m.group(1), ocr_blocks)
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

        # 7. Рабочий объём двигателя (куб. см)
        disp_m = re.search(r'11\.\s*Рабочий\s*объем[^\d]*(\d{3,5})\b', flat_text, re.IGNORECASE)
        if disp_m:
            disp_val = disp_m.group(1) + " куб. см"
            bbox, page = find_field_bbox(disp_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="engine_displacement",
                    display_name="Рабочий объём двигателя",
                    value=disp_val,
                    field_type="TEXT",
                    confidence=0.94,
                    bbox=bbox,
                    page=page
                )
            )

        # 8. Тип двигателя
        eng_type_m = re.search(r'12\.\s*Тип\s*двигателя\s*[:\.]?\s*([A-Za-zА-Яа-я]+)', flat_text, re.IGNORECASE)
        if eng_type_m:
            raw_eng = eng_type_m.group(1).strip().upper()
            if 'БЕНЗ' in raw_eng or 'БВНЗ' in raw_eng:
                eng_val = 'БЕНЗИНОВЫЙ'
            elif 'ДИЗ' in raw_eng:
                eng_val = 'ДИЗЕЛЬНЫЙ'
            elif 'ЭЛЕКТР' in raw_eng:
                eng_val = 'ЭЛЕКТРИЧЕСКИЙ'
            else:
                eng_val = raw_eng
            bbox, page = find_field_bbox(eng_type_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="engine_type",
                    display_name="Тип двигателя",
                    value=eng_val,
                    field_type="TEXT",
                    confidence=0.93,
                    bbox=bbox,
                    page=page
                )
            )

        # 9. Экологический класс
        eco_m = re.search(r'13\.\s*Экологический\s*класс\s*[:\.]?\s*([А-Яа-яA-Za-z0-9]+)', flat_text, re.IGNORECASE)
        if eco_m:
            eco_val = eco_m.group(1).strip().upper()
            bbox, page = find_field_bbox(eco_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="eco_class",
                    display_name="Экологический класс",
                    value=eco_val,
                    field_type="TEXT",
                    confidence=0.91,
                    bbox=bbox,
                    page=page
                )
            )

        # 10. Разрешенная максимальная масса, кг
        max_w_m = re.search(r'14\.\s*Разрешенная\s*максимальная\s*масса[^\d]*(\d{3,6})\b', flat_text, re.IGNORECASE)
        if max_w_m:
            mw_val = max_w_m.group(1) + " кг"
            bbox, page = find_field_bbox(max_w_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="max_weight",
                    display_name="Разрешённая макс. масса",
                    value=mw_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 11. Масса без нагрузки, кг
        unl_w_m = re.search(r'15\.\s*Масса\s*без\s*нагрузки[^\d]*(\d{3,6})\b', flat_text, re.IGNORECASE)
        if unl_w_m:
            uw_val = unl_w_m.group(1) + " кг"
            bbox, page = find_field_bbox(unl_w_m.group(1), ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="unladen_weight",
                    display_name="Масса без нагрузки",
                    value=uw_val,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 12. Организация-изготовитель ТС (страна)
        maker_m = re.search(r'16\.\s*Организация[\-\s]*изготовитель[^\:]*?[:\.]?\s*([A-Za-zА-Яа-я0-9\s\(\)\"]+?)(?=\s*17\.|\s*Одобрение|$)', flat_text, re.IGNORECASE)
        if maker_m:
            maker_val = maker_m.group(1).strip()
            if len(maker_val) >= 3:
                bbox, page = find_field_bbox(maker_val, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="manufacturer",
                        display_name="Организация-изготовитель",
                        value=maker_val,
                        field_type="ORGANIZATION",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 13. Наименование (ФИО) собственника ТС
        owner_m = re.search(r'21\.\s*Наименование[^\:]*?[:\.]?\s*([\"A-Za-zА-Яа-я0-9\s\.\-]+?)(?=\s*22\.|\s*Адрес|$)', flat_text, re.IGNORECASE)
        if owner_m:
            owner_val = owner_m.group(1).strip()
            if len(owner_val) >= 3:
                bbox, page = find_field_bbox(owner_val, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="owner_name",
                        display_name="Собственник ТС",
                        value=owner_val,
                        field_type="ORGANIZATION",
                        confidence=0.93,
                        bbox=bbox,
                        page=page
                    )
                )

        # 14. Адрес собственника ТС
        addr_m = re.search(r'22\.\s*Адрес\s*[:\.]?\s*([A-Za-zА-Яа-я0-9\s\.\,\-\/]+?)(?=\s*23\.|\s*Наименование|$)', flat_text, re.IGNORECASE)
        if addr_m:
            addr_val = addr_m.group(1).strip()
            if len(addr_val) >= 5:
                bbox, page = find_field_bbox(addr_val, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="owner_address",
                        display_name="Адрес собственника",
                        value=addr_val,
                        field_type="TEXT",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 15. Наименование организации, выдавшей паспорт
        issuer_m = re.search(r'23\.\s*Наименование\s*организации[^\:]*?[:\.]?\s*([A-Za-zА-Яа-я0-9\s\.\-]+?)(?=\s*24\.|\s*Адрес|$)', flat_text, re.IGNORECASE)
        if issuer_m:
            iss_val = issuer_m.group(1).strip()
            if len(iss_val) >= 4:
                bbox, page = find_field_bbox(iss_val, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="issued_by",
                        display_name="Кем выдан ПТС",
                        value=iss_val,
                        field_type="ORGANIZATION",
                        confidence=0.94,
                        bbox=bbox,
                        page=page
                    )
                )

        # 16. Дата выдачи паспорта
        date_m = re.search(r'25\.\s*(?:Дата\s*выдачи|паспорта)?[^\d]*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        if date_m:
            d_val = date_m.group(1).replace('/', '.')
            bbox, page = find_field_bbox(d_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="issue_date",
                    display_name="Дата выдачи ПТС",
                    value=d_val,
                    field_type="DATE",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        return fields

