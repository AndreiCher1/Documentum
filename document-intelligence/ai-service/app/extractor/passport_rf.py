"""
Экстрактор реквизитов Паспорта Гражданина РФ.

Извлекаемые ключевые поля:
- Серия и номер паспорта (формат 4 цифры + 6 цифр, с валидацией MRZ)
- Код подразделения (формат XXX-XXX)
- Дата выдачи (ДД.ММ.ГГГГ)
- Кем выдан (орган, выдавший документ: МВД, УФМС, ОВД)
- Фамилия, Имя, Отчество (сборное поле ФИО)
- Дата рождения
- Пол (МУЖ. / ЖЕН.)
- Место рождения
- Машиночитаемая зона (MRZ строки)
"""

import re
from typing import Any, List, Optional, Tuple

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox
from app.extractor.fms_units import validate_and_refine_issued_by, get_canonical_issued_by, get_region_name_by_code


# Таблица транслитерации «модернизированный клер» для внутренних паспортов РФ (Приказ ФМС РФ № 279 от 30.06.2011)
MODERNIZED_CLER_MAP = {
    'A': 'А', 'B': 'Б', 'V': 'В', 'G': 'Г', 'D': 'Д',
    'E': 'Е', '2': 'Ё', 'J': 'Ж', 'Z': 'З', 'I': 'И',
    'Q': 'Й', 'K': 'К', 'L': 'Л', 'M': 'М', 'N': 'Н',
    'O': 'О', 'P': 'П', 'R': 'Р', 'S': 'С', 'T': 'Т',
    'U': 'У', 'F': 'Ф', 'H': 'Х', 'C': 'Ц', '3': 'Ч',
    '4': 'Ш', 'W': 'Щ', 'X': 'Ъ', 'Y': 'Ы', '9': 'Ь',
    '6': 'Э', '7': 'Ю', '8': 'Я'
}


def decode_cler_part(part: str) -> str:
    """Декодирует латинские символы и специальные цифры МЧЗ в русские буквы по приказу ФМС № 279."""
    return "".join(MODERNIZED_CLER_MAP.get(ch, ch) for ch in part)


class PassportRfExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из паспорта РФ."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        flat_text = " ".join(lines)

        # Защита от ошибочного парсинга квитанций ЖКУ и счетов
        if re.search(r'итого\s+к\s+оплате|начислено|природный\s+газ|куб\.?\s*м|варочная\s+панель|перерасч[её]т', flat_text, re.IGNORECASE):
            return []

        # ---------------------------------------------------------
        # 0. Поиск и расшифровка MRZ строк (Машиночитаемая зона)
        # ---------------------------------------------------------
        mrz_line1: Optional[str] = None
        mrz_line2: Optional[str] = None
        mrz1_block = None
        mrz2_block = None

        for block in (ocr_blocks or []):
            b_text = getattr(block, 'text', '') if hasattr(block, 'text') else str(block)
            b_text_clean = b_text.strip()
            if 'RUS' in b_text_clean:
                if re.search(r'P[<A-Za-z0-9]*RUS', b_text_clean):
                    mrz_line1 = b_text_clean
                    mrz1_block = block
                elif re.search(r'\d{3,}[A-Za-z0-9]*RUS', b_text_clean):
                    mrz_line2 = b_text_clean
                    mrz2_block = block

        # Извлечение данных из MRZ line 2
        mrz_subdivision_code: Optional[str] = None
        mrz_series_number: Optional[str] = None
        mrz_birth_date: Optional[str] = None
        mrz_issue_date: Optional[str] = None
        mrz_gender: Optional[str] = None

        if mrz_line2:
            clean_m2 = re.sub(r'\s+', '', mrz_line2)
            # Формат строки 2 паспорта РФ:
            # 0..2: серия_1 (3 цифры), 3..8: номер (6 цифр), 9: к.ч., 10..12: RUS
            # 13..18: дата_рожд (YYMMDD), 19: к.ч., 20: пол (M/F), 21..27: разделители
            # 28: серия_2 (4-я цифра), 29..34: дата_выдачи (YYMMDD), 35..40: код_подразделения (6 цифр)
            m_full = re.search(r'(\d{3})(\d{6})\dRUS(\d{6})\d([MF])<{0,7}(\d)(\d{6})(\d{6})', clean_m2)
            if m_full:
                s1, num, b_raw, sex, s2, i_raw, c_raw = m_full.groups()
                mrz_series_number = f"{s1[:2]} {s1[2:]}{s2} {num}"
                century_b = "19" if int(b_raw[:2]) > 25 else "20"
                mrz_birth_date = f"{b_raw[4:6]}.{b_raw[2:4]}.{century_b}{b_raw[:2]}"
                century_i = "19" if int(i_raw[:2]) > 70 else "20"
                mrz_issue_date = f"{i_raw[4:6]}.{i_raw[2:4]}.{century_i}{i_raw[:2]}"
                mrz_gender = "МУЖ." if sex == "M" else "ЖЕН."
                mrz_subdivision_code = f"{c_raw[:3]}-{c_raw[3:]}"
            else:
                # Частичный парсинг по регулярным выражениям
                m_code = re.search(r'(\d{3})(\d{3})<', clean_m2)
                if m_code:
                    mrz_subdivision_code = f"{m_code.group(1)}-{m_code.group(2)}"
                m_dates = re.search(r'RUS(\d{2})(\d{2})(\d{2})\d([MF])', clean_m2)
                if m_dates:
                    yy, mm, dd, g = m_dates.groups()
                    century = "19" if int(yy) > 25 else "20"
                    mrz_birth_date = f"{dd}.{mm}.{century}{yy}"
                    mrz_gender = "МУЖ." if g == 'M' else "ЖЕН."

        # Извлечение ФИО из MRZ line 1 по стандарту «модернизированный клер»
        mrz_fio: Optional[str] = None
        if mrz_line1:
            m1 = re.search(r'P[<A-Za-z0-9]*RUS([A-Za-z0-9<]+)', mrz_line1)
            if m1:
                raw_parts = [p for p in m1.group(1).split('<') if p]
                dec_parts = [decode_cler_part(p) for p in raw_parts]
                if dec_parts:
                    mrz_fio = " ".join(dec_parts[:3])

        # ---------------------------------------------------------
        # 1. Код подразделения (XXX-XXX)
        # ---------------------------------------------------------
        subdivision_code_val = None
        subdivision_match = re.search(r'\b(\d{3}\s*[-—–]\s*\d{3})\b', flat_text)
        if subdivision_match:
            raw_code = subdivision_match.group(1)
            subdivision_code_val = re.sub(r'\s+', '', raw_code).replace('—', '-').replace('–', '-')
            bbox, page = find_field_bbox(subdivision_code_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="subdivision_code",
                    display_name="Код подразделения",
                    value=subdivision_code_val,
                    field_type="TEXT",
                    confidence=0.99,
                    bbox=bbox,
                    page=page
                )
            )
        elif mrz_subdivision_code:
            subdivision_code_val = mrz_subdivision_code
            bbox = getattr(mrz2_block, 'bbox', None)
            page = getattr(mrz2_block, 'page', 1)
            fields.append(
                ExtractedFieldValue(
                    name="subdivision_code",
                    display_name="Код подразделения",
                    value=subdivision_code_val,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # ---------------------------------------------------------
        # 2. Серия и номер паспорта (4 цифры серии + 6 цифр номера)
        # ---------------------------------------------------------
        series_num_match = re.search(r'\b(\d{2}\s*\d{2})\s*(?:№|N|No|#)?\s*(\d{6})\b', flat_text)
        if series_num_match:
            series = re.sub(r'\s+', '', series_num_match.group(1))
            number = series_num_match.group(2)
            full_series_number = f"{series[:2]} {series[2:]} {number}"
            bbox, page = find_field_bbox(number, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="series_number",
                    display_name="Серия и номер",
                    value=full_series_number,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )
        else:
            fallback_match = re.search(r'\b(\d{4})\s*(\d{6})\b', flat_text)
            if fallback_match:
                full_val = f"{fallback_match.group(1)[:2]} {fallback_match.group(1)[2:]} {fallback_match.group(2)}"
                bbox, page = find_field_bbox(fallback_match.group(2), ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="series_number",
                        display_name="Серия и номер",
                        value=full_val,
                        field_type="TEXT",
                        confidence=0.95,
                        bbox=bbox,
                        page=page
                    )
                )
            elif mrz_series_number:
                bbox = getattr(mrz2_block, 'bbox', None)
                page = getattr(mrz2_block, 'page', 1)
                fields.append(
                    ExtractedFieldValue(
                        name="series_number",
                        display_name="Серия и номер",
                        value=mrz_series_number,
                        field_type="TEXT",
                        confidence=0.98,
                        bbox=bbox,
                        page=page
                    )
                )
            else:
                # Поиск 6-значного номера и серии в вертикальных блоках на правом поле
                best_match = None
                for b in (ocr_blocks or []):
                    b_txt = getattr(b, 'text', '').strip()
                    m6 = re.search(r'\b(\d{6})\b', b_txt)
                    if m6 and len(b_txt) <= 8:
                        num = m6.group(1)
                        b_page = getattr(b, 'page', 1)
                        b_bbox = getattr(b, 'bbox', None)

                        if b_bbox:
                            cx = (b_bbox[0] + b_bbox[2]) / 2
                            col_blocks = []
                            for other in (ocr_blocks or []):
                                if other == b:
                                    continue
                                obbox = getattr(other, 'bbox', None)
                                if obbox and abs((obbox[0] + obbox[2]) / 2 - cx) < 60:
                                    col_blocks.append(other)

                            above = [cb for cb in col_blocks if getattr(cb, 'bbox', [0, 0, 0, 0])[1] < b_bbox[1]]
                            above.sort(key=lambda x: getattr(x, 'bbox', [0, 0, 0, 0])[1])

                            two_blocks = [cb for cb in above if re.fullmatch(r'\d{2}', getattr(cb, 'text', '').strip())]
                            if len(two_blocks) >= 2:
                                t1, t2 = two_blocks[-2], two_blocks[-1]
                                series_val = f"{getattr(t1, 'text', '').strip()} {getattr(t2, 'text', '').strip()}"
                                tb1, tb2 = getattr(t1, 'bbox', b_bbox), getattr(t2, 'bbox', b_bbox)
                                comb_bbox = [
                                    min(tb1[0], tb2[0], b_bbox[0]),
                                    min(tb1[1], tb2[1], b_bbox[1]),
                                    max(tb1[2], tb2[2], b_bbox[2]),
                                    max(tb1[3], tb2[3], b_bbox[3])
                                ]
                                best_match = (f"{series_val} {num}", comb_bbox, b_page, 0.98)
                                break

                            four_blocks = [cb for cb in above if re.fullmatch(r'\d{4}|\d{2}\s*\d{2}', getattr(cb, 'text', '').strip())]
                            if four_blocks:
                                f_blk = four_blocks[-1]
                                s_clean = re.sub(r'\s+', '', getattr(f_blk, 'text', '').strip())
                                fb = getattr(f_blk, 'bbox', b_bbox)
                                comb_bbox = [
                                    min(fb[0], b_bbox[0]),
                                    min(fb[1], b_bbox[1]),
                                    max(fb[2], b_bbox[2]),
                                    max(fb[3], b_bbox[3])
                                ]
                                best_match = (f"{s_clean[:2]} {s_clean[2:]} {num}", comb_bbox, b_page, 0.96)
                                break

                        if not best_match:
                            best_match = (f"№ {num}", b_bbox, b_page, 0.88)

                if best_match:
                    full_val, final_bbox, final_page, conf = best_match
                    fields.append(
                        ExtractedFieldValue(
                            name="series_number",
                            display_name="Серия и номер",
                            value=full_val,
                            field_type="TEXT",
                            confidence=conf,
                            bbox=final_bbox,
                            page=final_page
                        )
                    )

        # ---------------------------------------------------------
        # 3. Даты: Дата выдачи и Дата рождения
        # ---------------------------------------------------------
        issue_date_val = None
        issue_date_box = None
        birth_date_val = None
        birth_date_box = None

        # Ищем дату выдачи
        issue_match = re.search(
            r'(?:дата\s*вы[дл]ачи|выдан[ао]?)\s*[:\.]?\s*(\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4})',
            flat_text,
            re.IGNORECASE
        )
        if issue_match:
            issue_date_val = re.sub(r'\s+', '', issue_match.group(1))
            issue_date_box, page = find_field_bbox(issue_date_val, ocr_blocks)
        else:
            # Ищем блок даты в верхней части (Y < 450)
            for b in (ocr_blocks or []):
                btxt = getattr(b, 'text', '').strip()
                bbox = getattr(b, 'bbox', [0, 0, 0, 0])
                if bbox[1] < 450 and re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', btxt):
                    issue_date_val = btxt
                    issue_date_box = bbox
                    break
            if not issue_date_val and mrz_issue_date:
                issue_date_val = mrz_issue_date
                issue_date_box = getattr(mrz2_block, 'bbox', None)

        if issue_date_val:
            fields.append(
                ExtractedFieldValue(
                    name="issue_date",
                    display_name="Дата выдачи",
                    value=issue_date_val,
                    field_type="DATE",
                    confidence=0.98,
                    bbox=issue_date_box,
                    page=1
                )
            )

        # Ищем дату рождения
        birth_match = re.search(
            r'(?:дата\s*рождения|родился|родилась|[ΔДд]ara\s*рождения)\s*[:\.]?\s*(\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4})',
            flat_text,
            re.IGNORECASE
        )
        if birth_match:
            birth_date_val = re.sub(r'\s+', '', birth_match.group(1))
            birth_date_box, page = find_field_bbox(birth_date_val, ocr_blocks)
        else:
            # Ищем дату в нижней половине страницы (Y >= 450)
            for b in (ocr_blocks or []):
                btxt = getattr(b, 'text', '').strip()
                bbox = getattr(b, 'bbox', [0, 0, 0, 0])
                if bbox[1] >= 450 and re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', btxt):
                    birth_date_val = btxt
                    birth_date_box = bbox
                    break
            if not birth_date_val and mrz_birth_date:
                birth_date_val = mrz_birth_date
                birth_date_box = getattr(mrz2_block, 'bbox', None)

        if birth_date_val:
            fields.append(
                ExtractedFieldValue(
                    name="birth_date",
                    display_name="Дата рождения",
                    value=birth_date_val,
                    field_type="DATE",
                    confidence=0.98,
                    bbox=birth_date_box,
                    page=1
                )
            )

        # ---------------------------------------------------------
        # 4. Пол (МУЖ. / ЖЕН.)
        # ---------------------------------------------------------
        gender_val = None
        gender_box = None
        gender_match = re.search(r'(?:пол|sex)\s*[:\.]?\s*(муж(?:\.|ской)?|жен(?:\.|ский)?|m|f)\b', flat_text, re.IGNORECASE)
        if gender_match:
            raw_g = gender_match.group(1).upper()
            gender_val = "МУЖ." if "МУЖ" in raw_g or raw_g == 'M' else "ЖЕН."
            gender_box, _ = find_field_bbox(gender_val[:3], ocr_blocks)
        elif mrz_gender:
            gender_val = mrz_gender
            gender_box = getattr(mrz2_block, 'bbox', None)

        if gender_val:
            fields.append(
                ExtractedFieldValue(
                    name="gender",
                    display_name="Пол",
                    value=gender_val,
                    field_type="TEXT",
                    confidence=0.97,
                    bbox=gender_box,
                    page=1
                )
            )

        # ---------------------------------------------------------
        # 5. ФИО (Фамилия, Имя, Отчество)
        # ---------------------------------------------------------
        # Двусторонняя сверка VIZ (визуальной зоны) и MRZ (машиночитаемой зоны)
        final_fio = None
        final_fio_bbox = None
        final_fio_conf = 0.95

        # Попытка извлечения из визуальной зоны по меткам
        surname_m = re.search(r'фамилия\s*[:\.]?\s*([а-яё\-]+)', flat_text, re.IGNORECASE)
        name_m = re.search(r'имя\s*[:\.]?\s*([а-яё\-]+)', flat_text, re.IGNORECASE)
        patr_m = re.search(r'отчество\s*[:\.]?\s*([а-яё\-]+)', flat_text, re.IGNORECASE)

        viz_fio = None
        viz_bbox = None
        if surname_m and name_m:
            s = surname_m.group(1).upper()
            n = name_m.group(1).upper()
            p = patr_m.group(1).upper() if patr_m else ""
            viz_fio = f"{s} {n} {p}".strip()
            viz_bbox, _ = find_field_bbox(s, ocr_blocks)

        # Если явных меток нет, собираем чистые кириллические блоки в зоне ФИО над датой рождения
        if not viz_fio:
            fio_cands = []
            max_fio_y = birth_date_box[1] if birth_date_box else 700
            for b in (ocr_blocks or []):
                txt = getattr(b, 'text', '').strip()
                bbox = getattr(b, 'bbox', [0, 0, 0, 0])
                if 450 <= bbox[1] < max_fio_y:
                    if re.fullmatch(r'[А-ЯЁ]{3,}', txt) and not re.search(r'паспорт|россия|федерация|рождения|место|жительства|личный', txt, re.IGNORECASE):
                        if b.confidence >= 0.70:
                            fio_cands.append(b)
            if len(fio_cands) >= 2:
                fio_cands.sort(key=lambda b: getattr(b, 'bbox', [0, 0, 0, 0])[1])
                viz_fio = " ".join(getattr(b, 'text', '').strip() for b in fio_cands[:3])
                viz_bbox = [
                    min(getattr(b, 'bbox', [0, 0, 0, 0])[0] for b in fio_cands[:3]),
                    min(getattr(b, 'bbox', [0, 0, 0, 0])[1] for b in fio_cands[:3]),
                    max(getattr(b, 'bbox', [0, 0, 0, 0])[2] for b in fio_cands[:3]),
                    max(getattr(b, 'bbox', [0, 0, 0, 0])[3] for b in fio_cands[:3])
                ]

        # Синтез и арбитраж между VIZ и MRZ
        if mrz_fio:
            # MRZ line 1 расшифрован по «модернизированному клеру»
            final_fio = mrz_fio
            final_fio_bbox = viz_bbox if viz_bbox else getattr(mrz1_block, 'bbox', None)
            final_fio_conf = 0.99 if viz_fio and viz_fio == mrz_fio else 0.97
        elif viz_fio:
            final_fio = viz_fio
            final_fio_bbox = viz_bbox
            final_fio_conf = 0.94

        if final_fio:
            fields.append(
                ExtractedFieldValue(
                    name="fio",
                    display_name="ФИО",
                    value=final_fio,
                    field_type="PERSON",
                    confidence=final_fio_conf,
                    bbox=final_fio_bbox,
                    page=1
                )
            )

        # ---------------------------------------------------------
        # 6. Кем выдан (орган выдачи)
        # ---------------------------------------------------------
        # Многострочная сборка (Multi-Line Merging) с отсечением типографского мусора
        auth_candidates = []
        max_auth_y = issue_date_box[1] if issue_date_box else 300
        min_auth_y = 130

        # Стоп-слова и типографские заголовки бланка паспорта
        anchor_stop_terms = [
            "паспорт", "выдан", "восторт", "воспорт", "российская", "федерация",
            "дата", "выдачи", "код", "подразделения", "личный", "подпись"
        ]

        for b in (ocr_blocks or []):
            b_box = getattr(b, 'bbox', None)
            b_txt = getattr(b, 'text', '').strip()
            if not b_box or b.confidence < 0.60:
                continue

            # Должен находиться в верхней части страницы (над датой выдачи)
            if min_auth_y <= b_box[1] <= max_auth_y + 15:
                # Исключаем вертикальную колонку серии/номера на правом поле
                if b_box[0] > 1050 or re.fullmatch(r'\d{1,6}', b_txt):
                    continue
                # Исключаем дату выдачи и код подразделения
                if re.search(r'\d{2}\.\d{2}\.\d{4}|\d{3}-\d{3}', b_txt):
                    continue

                # Проверка на совпадение со стоп-метками типографики бланка
                is_anchor = any(term in b_txt.lower() for term in anchor_stop_terms)
                if is_anchor and len(b_txt.split()) <= 2:
                    continue

                auth_candidates.append(b)

        assembled_raw = ""
        issued_bbox = None
        if auth_candidates:
            # Топологическая сортировка: сверху вниз, слева направо
            auth_candidates.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
            assembled_raw = " ".join(b.text.strip() for b in auth_candidates)
            issued_bbox = [
                min(b.bbox[0] for b in auth_candidates),
                min(b.bbox[1] for b in auth_candidates),
                max(b.bbox[2] for b in auth_candidates),
                max(b.bbox[3] for b in auth_candidates)
            ]

        # Валидация и восстановление наименования через справочник подразделений МВД/ФМС
        refined_issued_by, issued_conf = validate_and_refine_issued_by(assembled_raw, subdivision_code_val)

        if refined_issued_by:
            fields.append(
                ExtractedFieldValue(
                    name="issued_by",
                    display_name="Кем выдан",
                    value=refined_issued_by,
                    field_type="ORGANIZATION",
                    confidence=issued_conf,
                    bbox=issued_bbox if issued_bbox else issue_date_box,
                    page=1
                )
            )

        return fields
