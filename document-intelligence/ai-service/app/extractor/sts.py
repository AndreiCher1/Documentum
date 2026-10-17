"""
Экстрактор реквизитов Свидетельства о регистрации транспортного средства (СТС).

Извлекаемые ключевые поля:
- Государственный регистрационный знак (госномер)
- Идентификационный номер (VIN, 17 символов)
- Марка, модель ТС (например, BMW 750i)
- Тип ТС (СЕДАН ЛЕГКОВОЙ, ХЭТЧБЕК и др.)
- Категория ТС (A, B, C, D, прицеп)
- Год выпуска ТС
- Модель двигателя / Номер двигателя
- Кузов (кабина, прицеп) № / Шасси (рама) №
- Цвет кузова
- Мощность двигателя (кВт / л.с.)
- Рабочий объем двигателя (см³)
- Паспорт ТС (серия и номер ПТС)
- Разрешенная максимальная масса (кг)
- Масса без нагрузки (кг)
- Серия и номер бланка СТС
- Собственник (ФИО / Наименование) и адрес
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


def _format_vehicle_model(model_str: str) -> str:
    """Нормализует написание марки и модели (например: 'BMW750I' -> 'BMW 750i')."""
    if not model_str:
        return model_str
    clean = model_str.strip()
    
    # Известные бренды, если они слились с серией/моделью без пробела
    brands = [
        "BMW", "MERCEDES-BENZ", "MERCEDES", "AUDI", "VOLKSWAGEN", "VW", "TOYOTA",
        "LEXUS", "NISSAN", "INFINITI", "HONDA", "MAZDA", "MITSUBISHI", "SUBARU",
        "HYUNDAI", "KIA", "GENESIS", "SKODA", "RENAULT", "PEUGEOT", "CITROEN",
        "VOLVO", "PORSCHE", "LAND ROVER", "JAGUAR", "CHEVROLET", "FORD", "OPEL",
        "LADA", "ВАЗ", "ГАЗ", "УАЗ", "КАМАЗ", "CHERY", "HAVAL", "GEELY", "CHANGAN"
    ]
    for b in brands:
        pattern = r'^(' + re.escape(b) + r')([A-Za-z0-9\-]+)$'
        m = re.match(pattern, clean, re.IGNORECASE)
        if m:
            brand_part = m.group(1).upper()
            model_part = m.group(2)
            # Если модель вроде 750I -> 750i
            if model_part.endswith('I') and model_part[:-1].isdigit():
                model_part = model_part[:-1] + 'i'
            return f"{brand_part} {model_part}"

    return clean


class StsExtractor(BaseFieldExtractor):
    """Гибридный пространственно-семантический экстрактор данных СТС."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text and not ocr_blocks:
            return fields

        flat_text = " ".join(text.split()) if text else ""

        # ---------------------------------------------------------
        # 1. Государственный регистрационный знак (госномер)
        # ---------------------------------------------------------
        p_val, p_bbox, p_page = find_spatial_field(
            r'регистрацион\w*\s*знак|гос\s*номер',
            ocr_blocks,
            value_filter=lambda v: bool(re.search(r'[А-Яа-яA-Za-z0-9]{6,10}', v))
        )
        if not p_val:
            plate_m = re.search(r'\b([АВЕКМНОРСТУХA-Z]{1}\s*\d{3}\s*[АВЕКМНОРСТУХA-Z]{2}\s*\d{2,3})\b', flat_text, re.IGNORECASE)
            if plate_m:
                p_val = plate_m.group(1)
                p_bbox, p_page = find_field_bbox(plate_m.group(1), ocr_blocks)

        if p_val:
            # Нормализация госномера (удаление лишних знаков, перевод в верхний регистр)
            p_val_clean = re.sub(r'[\s\.\-]+', '', p_val).upper()
            # Преобразуем латиницу в кириллицу для стандартных букв госномера
            homoglyphs = {'A': 'А', 'B': 'В', 'E': 'Е', 'K': 'К', 'M': 'М', 'H': 'Н', 'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т', 'Y': 'У', 'X': 'Х'}
            p_val_clean = "".join(homoglyphs.get(c, c) for c in p_val_clean)
            fields.append(
                ExtractedFieldValue(
                    name="plate_number",
                    display_name="Регистрационный знак",
                    value=p_val_clean,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=p_bbox,
                    page=p_page
                )
            )

        # ---------------------------------------------------------
        # 2. Идентификационный номер (VIN)
        # ---------------------------------------------------------
        v_raw, v_bbox, v_page = find_spatial_field(
            r'идентификацион\w*\s*номер|(?:\b|\()vin(?:\b|\))',
            ocr_blocks,
            value_filter=lambda v: len(re.sub(r'[^A-Za-z0-9]', '', v)) >= 14
        )
        vin_norm = normalize_vin(v_raw) if v_raw else None

        if not vin_norm:
            # Поиск в общем тексте с нормализацией
            for candidate in re.findall(r'\b([A-Za-z0-9]{17})\b', flat_text):
                norm = normalize_vin(candidate)
                if norm:
                    vin_norm = norm
                    v_bbox, v_page = find_field_bbox(candidate, ocr_blocks)
                    break

        if vin_norm:
            if not v_bbox:
                v_bbox, v_page = find_field_bbox(vin_norm, ocr_blocks)
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

        # ---------------------------------------------------------
        # 3. Марка, модель ТС
        # ---------------------------------------------------------
        m_val, m_bbox, m_page = find_spatial_field(
            r'марка,?\s*модель(?:\s*тс)?|марка\s*тс',
            ocr_blocks,
            value_filter=lambda v: len(v) >= 2 and not v.isdigit()
        )
        if not m_val:
            model_m = re.search(r'(?:марка,?\s*модель(?:\s*тс)?|марка)\s*[:\.]?\s*([A-Za-zА-Яа-я0-9\s\-]+?)(?=\s*тип\s*тс|\s*категория|\s*год\s*выпуска|$)', flat_text, re.IGNORECASE)
            if model_m:
                candidate = model_m.group(1).strip()
                if len(candidate) >= 2 and not candidate.isdigit():
                    m_val = candidate
                    m_bbox, m_page = find_field_bbox(candidate[:15], ocr_blocks)

        if m_val:
            formatted_model = _format_vehicle_model(m_val)
            fields.append(
                ExtractedFieldValue(
                    name="vehicle_model",
                    display_name="Марка, модель ТС",
                    value=formatted_model,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=m_bbox,
                    page=m_page
                )
            )

        # ---------------------------------------------------------
        # 4. Тип ТС
        # ---------------------------------------------------------
        t_val, t_bbox, t_page = find_spatial_field(
            r'тип\s*тс',
            ocr_blocks,
            value_filter=lambda v: len(v) >= 3 and not re.search(r'категория|год', v, re.I)
        )
        if not t_val:
            type_m = re.search(r'тип\s*тс\s*[:\.]?\s*([А-Яа-яA-Za-z\s\-]+?)(?=\s*категория|\s*год|\s*модель|\d|$)', flat_text, re.IGNORECASE)
            if type_m:
                t_val = type_m.group(1).strip()
                t_bbox, t_page = find_field_bbox(t_val, ocr_blocks)

        if t_val:
            fields.append(
                ExtractedFieldValue(
                    name="vehicle_type",
                    display_name="Тип ТС",
                    value=t_val.upper(),
                    field_type="TEXT",
                    confidence=0.94,
                    bbox=t_bbox,
                    page=t_page
                )
            )

        # ---------------------------------------------------------
        # 5. Категория ТС (A, B, C, D)
        # ---------------------------------------------------------
        c_val, c_bbox, c_page = find_spatial_field(
            r'категория(?:\s*тс)?',
            ocr_blocks,
            value_filter=lambda v: bool(re.search(r'[A-Da-dА-Ва-в]', v))
        )
        cat_extracted = None
        if c_val:
            cat_match = re.search(r'([A-Da-dА-Ва-в])(?:\b|$)', c_val)
            if cat_match:
                cat_extracted = cat_match.group(1).upper()
        if not cat_extracted:
            cat_m = re.search(r'категория(?:\s*тс)?.*?([A-Da-dА-Ва-в])\b', flat_text, re.IGNORECASE)
            if cat_m:
                cat_extracted = cat_m.group(1).upper()
                c_bbox, c_page = find_field_bbox(cat_m.group(1), ocr_blocks)

        if cat_extracted:
            cat_map = {"А": "A", "В": "B", "С": "C", "D": "D"}
            cat_extracted = cat_map.get(cat_extracted, cat_extracted)
            fields.append(
                ExtractedFieldValue(
                    name="vehicle_category",
                    display_name="Категория ТС",
                    value=cat_extracted,
                    field_type="TEXT",
                    confidence=0.96,
                    bbox=c_bbox,
                    page=c_page
                )
            )

        # ---------------------------------------------------------
        # 6. Год выпуска ТС
        # ---------------------------------------------------------
        y_val, y_bbox, y_page = find_spatial_field(
            r'год\s*выпуска(?:\s*тс)?',
            ocr_blocks,
            value_filter=lambda v: bool(re.search(r'\b(?:19\d{2}|20\d{2})\b', v))
        )
        year_str = None
        if y_val:
            ym = re.search(r'\b(19\d{2}|20\d{2})\b', y_val)
            if ym:
                year_str = ym.group(1)
        if not year_str:
            ym = re.search(r'год\s*выпуска(?:\s*тс)?\s*[:\.]?\s*(19\d{2}|20\d{2})\b', flat_text, re.IGNORECASE)
            if ym:
                year_str = ym.group(1)
                y_bbox, y_page = find_field_bbox(year_str, ocr_blocks)

        if year_str:
            fields.append(
                ExtractedFieldValue(
                    name="manufacture_year",
                    display_name="Год выпуска ТС",
                    value=year_str,
                    field_type="YEAR",
                    confidence=0.96,
                    bbox=y_bbox,
                    page=y_page
                )
            )

        # ---------------------------------------------------------
        # 7. Модель двигателя
        # ---------------------------------------------------------
        em_val, em_bbox, em_page = find_spatial_field(
            r'модель\s*двигател\w*',
            ocr_blocks,
            value_filter=lambda v: len(v) >= 3 and not re.search(r'двигатель\s*№', v, re.I)
        )
        if em_val:
            fields.append(
                ExtractedFieldValue(
                    name="engine_model",
                    display_name="Модель двигателя",
                    value=em_val.strip().upper(),
                    field_type="TEXT",
                    confidence=0.93,
                    bbox=em_bbox,
                    page=em_page
                )
            )

        # ---------------------------------------------------------
        # 8. Двигатель №
        # ---------------------------------------------------------
        en_val, en_bbox, en_page = find_spatial_field(
            r'двигател\w*\s*№',
            ocr_blocks,
            value_filter=lambda v: len(re.sub(r'[^A-Za-z0-9]', '', v)) >= 4
        )
        if not en_val:
            eng_m = re.search(r'двигател\w*\s*№\s*[:\.]?\s*([A-Za-z0-9\-]+)', flat_text, re.IGNORECASE)
            if eng_m:
                en_val = eng_m.group(1)
                en_bbox, en_page = find_field_bbox(en_val, ocr_blocks)

        if en_val:
            en_val_clean = re.sub(r'^[oO0№\s\.]+', '', en_val).strip()
            if len(en_val_clean) >= 3:
                fields.append(
                    ExtractedFieldValue(
                        name="engine_number",
                        display_name="Двигатель №",
                        value=en_val_clean.upper(),
                        field_type="TEXT",
                        confidence=0.94,
                        bbox=en_bbox,
                        page=en_page
                    )
                )

        # ---------------------------------------------------------
        # 9. Шасси (рама) №
        # ---------------------------------------------------------
        ch_val, ch_bbox, ch_page = find_spatial_field(
            r'шасси\s*\(рама\)\s*№?',
            ocr_blocks,
            value_filter=lambda v: len(re.sub(r'[^A-Za-z0-9А-Яа-я]', '', v)) >= 3
        )
        if ch_val and not re.search(r'кузов|цвет|отсутствует', ch_val, re.I):
            fields.append(
                ExtractedFieldValue(
                    name="chassis_number",
                    display_name="Шасси (рама) №",
                    value=ch_val.strip().upper(),
                    field_type="TEXT",
                    confidence=0.91,
                    bbox=ch_bbox,
                    page=ch_page
                )
            )

        # ---------------------------------------------------------
        # 10. Кузов (кабина, прицеп) №
        # ---------------------------------------------------------
        b_val, b_bbox, b_page = find_spatial_field(
            r'кузов\s*\((?:кабина|коляска|прицеп)\)?\s*№?',
            ocr_blocks,
            value_filter=lambda v: len(re.sub(r'[^A-Za-z0-9]', '', v)) >= 3
        )
        if not b_val:
            body_m = re.search(r'кузов\s*\((?:кабина|коляска|прицеп)\)?\s*№?\s*([A-Za-z0-9\-]+)', flat_text, re.IGNORECASE)
            if body_m:
                b_val = body_m.group(1)
                b_bbox, b_page = find_field_bbox(b_val, ocr_blocks)

        if b_val:
            clean_body = re.sub(r'^[oO№\s\.]+', '', b_val).strip()
            if len(clean_body) >= 3:
                fields.append(
                    ExtractedFieldValue(
                        name="body_number",
                        display_name="Кузов (коляска) №",
                        value=clean_body.upper(),
                        field_type="TEXT",
                        confidence=0.94,
                        bbox=b_bbox,
                        page=b_page
                    )
                )

        # ---------------------------------------------------------
        # 11. Цвет кузова
        # ---------------------------------------------------------
        c_val, c_bbox, c_page = find_spatial_field(
            r'цвет(?:\s*кузова)?',
            ocr_blocks,
            value_filter=lambda v: len(v) >= 3 and not re.search(r'мощность|двигатель|паспорт', v, re.I)
        )
        if not c_val:
            color_m = re.search(r'цвет(?:\s*кузова)?\s*[:\.]?\s*([А-Яа-яA-Za-z\s\-]+?)(?=\s*мощность|\s*экологический|\s*паспорт|\d|$)', flat_text, re.IGNORECASE)
            if color_m:
                candidate = color_m.group(1).strip()
                if len(candidate) >= 3 and not candidate.isdigit():
                    c_val = candidate
                    c_bbox, c_page = find_field_bbox(candidate, ocr_blocks)

        if c_val:
            fields.append(
                ExtractedFieldValue(
                    name="color",
                    display_name="Цвет кузова",
                    value=c_val.strip().upper(),
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=c_bbox,
                    page=c_page
                )
            )

        # ---------------------------------------------------------
        # 12. Мощность двигателя (кВт / л.с.)
        # ---------------------------------------------------------
        pwr_m = re.search(r'мощность\s*двигател\w*.*?(\d+[\d\.,\s]*(?:\/\s*\d+)?\s*(?:квт|л\.?\s*с\.?|квт\/л\.?\s*с\.?|\b))', flat_text, re.IGNORECASE)
        power_str = None
        pwr_bbox, pwr_page = None, 1
        if pwr_m:
            num_part = re.search(r'(\d+[\.,]?\d*\s*\/\s*\d+[\.,]?\d*|\d+[\.,]?\d*)', pwr_m.group(0))
            if num_part:
                power_str = num_part.group(1).replace(' ', '')
                pwr_bbox, pwr_page = find_field_bbox(power_str, ocr_blocks)
        if not power_str:
            pwr_val, pwr_bbox, pwr_page = find_spatial_field(
                r'мощность\s*двигател\w*',
                ocr_blocks,
                value_filter=lambda v: bool(re.search(r'\d+', v))
            )
            if pwr_val:
                num_part = re.search(r'(\d+[\.,]?\d*\s*\/\s*\d+[\.,]?\d*|\d+[\.,]?\d*)', pwr_val)
                if num_part:
                    power_str = num_part.group(1).replace(' ', '')

        if power_str:
            display_power = f"{power_str} кВт / л.с." if '/' in power_str else f"{power_str} л.с."
            fields.append(
                ExtractedFieldValue(
                    name="engine_power",
                    display_name="Мощность двигателя",
                    value=display_power,
                    field_type="TEXT",
                    confidence=0.93,
                    bbox=pwr_bbox,
                    page=pwr_page
                )
            )

        # ---------------------------------------------------------
        # 13. Рабочий объем двигателя (см³)
        # ---------------------------------------------------------
        vol_m = re.search(r'рабочий\s*объем\s*двигател\w*.*?(\d{3,5})\b', flat_text, re.IGNORECASE)
        vol_str, vol_bbox, vol_page = None, None, 1
        if vol_m:
            vol_str = vol_m.group(1)
            vol_bbox, vol_page = find_field_bbox(vol_str, ocr_blocks)
        else:
            v_val, vol_bbox, vol_page = find_spatial_field(
                r'рабочий\s*объем',
                ocr_blocks,
                value_filter=lambda v: bool(re.search(r'\d{3,5}', v))
            )
            if v_val:
                vm = re.search(r'\b(\d{3,5})\b', v_val)
                if vm:
                    vol_str = vm.group(1)

        if vol_str:
            fields.append(
                ExtractedFieldValue(
                    name="engine_displacement",
                    display_name="Рабочий объем двигателя",
                    value=f"{vol_str} см³",
                    field_type="TEXT",
                    confidence=0.94,
                    bbox=vol_bbox,
                    page=vol_page
                )
            )

        # ---------------------------------------------------------
        # 14. Паспорт ТС (серия и номер ПТС)
        # ---------------------------------------------------------
        pts_m = re.search(r'паспорт\s*(?:серия|тс|номер)?\s*[:\.]?\s*(\d{2}\s*[А-Яа-яA-Za-z]{2,3}\s*\d{6})\b', flat_text, re.IGNORECASE)
        if not pts_m:
            pts_m = re.search(r'\b(\d{2}\s*[А-Яа-яA-Za-z]{2,3}\s*\d{6})\b', flat_text, re.IGNORECASE)
        if pts_m:
            pts_val = pts_m.group(1).strip()
            # Форматируем красивую серию и номер (2 цифры + 2 буквы + 6 цифр)
            m_parts = re.match(r'^(\d{2})\s*([А-Яа-яA-Za-z]{2,3})\s*(\d{6})$', pts_val)
            if m_parts:
                pts_val = f"{m_parts.group(1)} {m_parts.group(2)[:2]} {m_parts.group(3)}".upper()
            pts_bbox, pts_page = find_field_bbox(pts_val[:5], ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="pts_series_number",
                    display_name="Паспорт ТС (серия и номер)",
                    value=pts_val.upper(),
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=pts_bbox,
                    page=pts_page
                )
            )

        # ---------------------------------------------------------
        # 15. Разрешенная max масса (кг)
        # ---------------------------------------------------------
        max_m_val, max_m_bbox, max_m_page = find_spatial_field(
            r'разрешенн\w*\s*(?:тах|max|максимальн\w*)?\s*масса',
            ocr_blocks,
            value_filter=lambda v: bool(re.search(r'\b\d{3,5}\b', v))
        )
        mass_max_str = None
        if max_m_val:
            mm = re.search(r'\b(\d{3,5})\b', max_m_val)
            if mm:
                mass_max_str = mm.group(1)
        if not mass_max_str:
            mass_max_m = re.search(r'разрешенная\s*(?:m[аa]x|тах|максимальная)?\s*масса(?:\s*,\s*кг)?\s*[:\.]?\s*(\d{3,5})\b', flat_text, re.IGNORECASE)
            if mass_max_m:
                mass_max_str = mass_max_m.group(1)
                max_m_bbox, max_m_page = find_field_bbox(mass_max_str, ocr_blocks)

        if mass_max_str:
            fields.append(
                ExtractedFieldValue(
                    name="max_weight",
                    display_name="Разрешенная max масса",
                    value=f"{mass_max_str} кг",
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=max_m_bbox,
                    page=max_m_page
                )
            )

        # ---------------------------------------------------------
        # 16. Масса без нагрузки (кг)
        # ---------------------------------------------------------
        unl_m_val, unl_m_bbox, unl_m_page = find_spatial_field(
            r'масса\s*без\s*нагрузки',
            ocr_blocks,
            value_filter=lambda v: bool(re.search(r'\b\d{3,5}\b', v))
        )
        mass_unl_str = None
        if unl_m_val:
            mm = re.search(r'\b(\d{3,5})\b', unl_m_val)
            if mm:
                mass_unl_str = mm.group(1)
        if not mass_unl_str:
            mass_unl_m = re.search(r'масса\s*без\s*нагрузки(?:\s*,\s*кг)?\s*[:\.]?\s*(\d{3,5})\b', flat_text, re.IGNORECASE)
            if mass_unl_m:
                mass_unl_str = mass_unl_m.group(1)
                unl_m_bbox, unl_m_page = find_field_bbox(mass_unl_str, ocr_blocks)

        if mass_unl_str:
            fields.append(
                ExtractedFieldValue(
                    name="unladen_mass",
                    display_name="Масса без нагрузки",
                    value=f"{mass_unl_str} кг",
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=unl_m_bbox,
                    page=unl_m_page
                )
            )

        # ---------------------------------------------------------
        # 17. Серия и номер бланка СТС
        # ---------------------------------------------------------
        sts_num_m = re.search(r'\b(\d{2}\s*[А-Яа-яA-Za-z0-9]{2}\s*\d{6})\b', flat_text)
        sts_num_val, sts_bbox, sts_page = None, None, 1
        if sts_num_m:
            sts_num_val = sts_num_m.group(1).strip()
            sts_bbox, sts_page = find_field_bbox(sts_num_val, ocr_blocks)
        elif ocr_blocks and len(ocr_blocks) >= 3:
            # Проверяем нижние блоки документа (обычно серия и номер бланка СТС печатаются внизу)
            last_blocks = sorted(ocr_blocks, key=lambda b: getattr(b, 'bbox', [0, 0, 0, 0])[1], reverse=True)[:5]
            last_texts = [getattr(b, 'text', '').strip() for b in reversed(last_blocks)]
            combined_bottom = " ".join(last_texts)
            bottom_m = re.search(r'\b(\d{2}\s+[А-Яа-яA-Za-z0-9]{2}\s+\d{6})\b', combined_bottom)
            if bottom_m:
                sts_num_val = bottom_m.group(1)
                sts_bbox = last_blocks[0].bbox
                sts_page = getattr(last_blocks[0], 'page', 1)

        if sts_num_val:
            fields.append(
                ExtractedFieldValue(
                    name="sts_number",
                    display_name="Серия и номер СТС",
                    value=sts_num_val.upper(),
                    field_type="TEXT",
                    confidence=0.97,
                    bbox=sts_bbox,
                    page=sts_page
                )
            )

        # ---------------------------------------------------------
        # 18. Собственник (ФИО) и адрес (для 2-й стороны СТС)
        # ---------------------------------------------------------
        owner_m = re.search(r'собственник\s*[:\.]?\s*([А-ЯЁ\s\-]{4,40}?)(?=\s*республика|\s*край|\s*область|\s*г\.|\s*район|\s*ул\.|$)', flat_text, re.IGNORECASE)
        if owner_m:
            owner_val = owner_m.group(1).strip()
            if len(owner_val.split()) >= 2:
                o_bbox, o_page = find_field_bbox(owner_val.split()[0], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="owner_name",
                        display_name="Собственник ТС",
                        value=owner_val,
                        field_type="PERSON_NAME",
                        confidence=0.92,
                        bbox=o_bbox,
                        page=o_page
                    )
                )

        return fields
