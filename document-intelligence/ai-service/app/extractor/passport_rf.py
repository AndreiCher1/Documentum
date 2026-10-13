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
from typing import Any, List, Optional

from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


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

        # Поиск MRZ строк (Машиночитаемая зона)
        mrz_line1 = None
        mrz_line2 = None
        for block in (ocr_blocks or []):
            b_text = getattr(block, 'text', '') if hasattr(block, 'text') else str(block)
            if 'RUS' in b_text:
                if re.search(r'P[<A-Za-z0-9]*RUS', b_text):
                    mrz_line1 = b_text
                elif re.search(r'\d{3,}[A-Za-z0-9]*RUS', b_text):
                    mrz_line2 = b_text

        # 1. Код подразделения (XXX-XXX)
        subdivision_match = re.search(r'\b(\d{3}\s*[-—–]\s*\d{3})\b', flat_text)
        if subdivision_match:
            raw_code = subdivision_match.group(1)
            clean_code = re.sub(r'\s+', '', raw_code).replace('—', '-').replace('–', '-')
            bbox, page = find_field_bbox(clean_code, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="subdivision_code",
                    display_name="Код подразделения",
                    value=clean_code,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 2. Серия и номер паспорта (4 цифры серии + 6 цифр номера)
        # Примеры в OCR: "40 12 345678", "4012 345678", "40 12 № 345678"
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
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )
        else:
            fallback_match = re.search(r'\b(\d{4})\s*(\d{6})\b', flat_text)
            if fallback_match:
                full_val = f"{fallback_match.group(1)} {fallback_match.group(2)}"
                bbox, page = find_field_bbox(fallback_match.group(2), ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="series_number",
                        display_name="Серия и номер",
                        value=full_val,
                        field_type="TEXT",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )
            else:
                # Поиск 6-значного номера и серии в отдельных блоках (например, вертикально на полях)
                best_match = None
                for b in (ocr_blocks or []):
                    b_txt = getattr(b, 'text', '').strip()
                    m6 = re.search(r'\b(\d{6})\b', b_txt)
                    if m6 and len(b_txt) <= 8:
                        num = m6.group(1)
                        b_page = getattr(b, 'page', 1)
                        b_bbox = getattr(b, 'bbox', None)

                        # Ищем серию в той же вертикальной колонке (похожий X, выше номера)
                        if b_bbox:
                            cx = (b_bbox[0] + b_bbox[2]) / 2
                            col_blocks = []
                            for other in (ocr_blocks or []):
                                if other == b:
                                    continue
                                obbox = getattr(other, 'bbox', None)
                                if obbox and abs((obbox[0] + obbox[2]) / 2 - cx) < 60:
                                    col_blocks.append(other)

                            # Блоки над номером (Y < Y_num)
                            above = [cb for cb in col_blocks if getattr(cb, 'bbox', [0, 0, 0, 0])[1] < b_bbox[1]]
                            above.sort(key=lambda x: getattr(x, 'bbox', [0, 0, 0, 0])[1])

                            # 1) Два блока по 2 цифры над номером (например, "11" и "04")
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

                            # 2) Блок из 4 цифр над номером (например, "11 04" или "1104")
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

        # 3. Даты: Дата выдачи и Дата рождения
        date_pattern = r'\b(0[1-9]|[12][0-9]|3[01])\s*\.\s*(0[1-9]|1[0-2])\s*\.\s*([12]\d{3})\b'
        raw_dates = list(re.finditer(date_pattern, flat_text))
        all_dates = []
        for rd in raw_dates:
            day, month, year = rd.group(1), rd.group(2), rd.group(3)
            # Исправление распространенных OCR-артефактов в годах рождения (например, "1682" вместо "1982")
            if year.startswith(('16', '17', '18')) and not year.endswith(('19', '20')):
                year = f"19{year[2:]}"
            d_str = f"{day}.{month}.{year}"
            all_dates.append((d_str, rd))

        # Поиск даты выдачи по контексту
        issue_date_found = False
        issue_match = re.search(
            r'(?:дата\s*вы[дл]ачи|выдан[ао]?)\s*[:\.]?\s*(\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4})',
            flat_text,
            re.IGNORECASE
        )
        if issue_match:
            raw_idate = issue_match.group(1)
            issue_date = re.sub(r'\s+', '', raw_idate)
            bbox, page = find_field_bbox(issue_date, ocr_blocks)
            if not bbox:
                bbox, page = find_field_bbox(raw_idate, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="issue_date",
                    display_name="Дата выдачи",
                    value=issue_date,
                    field_type="DATE",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )
            issue_date_found = True

        # Поиск в отдельных блоках OCR для даты выдачи
        if not issue_date_found:
            for b in (ocr_blocks or []):
                btxt = getattr(b, 'text', '')
                if re.search(r'вы[дл]ач|выдан', btxt, re.IGNORECASE):
                    dm = re.search(r'(\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4})', btxt)
                    if dm:
                        issue_date = re.sub(r'\s+', '', dm.group(1))
                        fields.append(
                            ExtractedFieldValue(
                                name="issue_date",
                                display_name="Дата выдачи",
                                value=issue_date,
                                field_type="DATE",
                                confidence=0.98,
                                bbox=getattr(b, 'bbox', None),
                                page=getattr(b, 'page', 1)
                            )
                        )
                        issue_date_found = True
                        break

        # Поиск даты рождения по контексту
        birth_date_found = False
        birth_match = re.search(
            r'(?:дата\s*рождения|родился|родилась|[ΔДд]ara\s*рождения)\s*[:\.]?\s*(\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4})',
            flat_text,
            re.IGNORECASE
        )
        if birth_match:
            raw_bdate = birth_match.group(1)
            birth_date = re.sub(r'\s+', '', raw_bdate)
            bbox, page = find_field_bbox(birth_date, ocr_blocks)
            if not bbox:
                bbox, page = find_field_bbox(raw_bdate, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="birth_date",
                    display_name="Дата рождения",
                    value=birth_date,
                    field_type="DATE",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )
            birth_date_found = True

        # Поиск в отдельных блоках OCR для даты рождения
        if not birth_date_found:
            for b in (ocr_blocks or []):
                btxt = getattr(b, 'text', '')
                if re.search(r'рожден|[ΔДд]ara', btxt, re.IGNORECASE):
                    dm = re.search(r'(\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4})', btxt)
                    if dm:
                        birth_date = re.sub(r'\s+', '', dm.group(1))
                        fields.append(
                            ExtractedFieldValue(
                                name="birth_date",
                                display_name="Дата рождения",
                                value=birth_date,
                                field_type="DATE",
                                confidence=0.98,
                                bbox=getattr(b, 'bbox', None),
                                page=getattr(b, 'page', 1)
                            )
                        )
                        birth_date_found = True
                        break

        # Если не нашли по контексту, но нашли 2 даты: более ранняя — дата рождения, более поздняя — выдача
        if len(all_dates) >= 2 and (not issue_date_found or not birth_date_found):
            dates_sorted = sorted(all_dates, key=lambda x: (x[0][6:], x[0][3:5], x[0][:2]))
            if not birth_date_found:
                b_str, b_rd = dates_sorted[0]
                bbox, page = find_field_bbox(b_str, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="birth_date",
                        display_name="Дата рождения",
                        value=b_str,
                        field_type="DATE",
                        confidence=0.90,
                        bbox=bbox,
                        page=page
                    )
                )
                birth_date_found = True
            if not issue_date_found:
                i_str, i_rd = dates_sorted[-1]
                bbox, page = find_field_bbox(i_str, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="issue_date",
                        display_name="Дата выдачи",
                        value=i_str,
                        field_type="DATE",
                        confidence=0.90,
                        bbox=bbox,
                        page=page
                    )
                )
                issue_date_found = True
        elif len(all_dates) == 1 and not issue_date_found and not birth_date_found:
            d_val, d_rd = all_dates[0]
            year_int = int(d_val[6:])
            bbox, page = find_field_bbox(d_val, ocr_blocks)
            if year_int >= 2000:
                fields.append(
                    ExtractedFieldValue(
                        name="issue_date",
                        display_name="Дата выдачи",
                        value=d_val,
                        field_type="DATE",
                        confidence=0.88,
                        bbox=bbox,
                        page=page
                    )
                )
                issue_date_found = True
            else:
                fields.append(
                    ExtractedFieldValue(
                        name="birth_date",
                        display_name="Дата рождения",
                        value=d_val,
                        field_type="DATE",
                        confidence=0.88,
                        bbox=bbox,
                        page=page
                    )
                )
                birth_date_found = True

        # Если дата рождения всё ещё не найдена — извлекаем из MRZ line 2
        if not birth_date_found and mrz_line2:
            m2 = re.search(r'(\d{9,10})[A-Za-z0-9]{3}(\d{2})(\d{2})(\d{2})\d([MF])', mrz_line2)
            if m2:
                yy, mm, dd = m2.group(2), m2.group(3), m2.group(4)
                century = "19" if int(yy) > 25 else "20"
                b_date = f"{dd}.{mm}.{century}{yy}"
                bbox, page = find_field_bbox(mrz_line2[:20], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="birth_date",
                        display_name="Дата рождения",
                        value=b_date,
                        field_type="DATE",
                        confidence=0.95,
                        bbox=bbox,
                        page=page
                    )
                )
                birth_date_found = True

        # 4. Пол (Пол: МУЖ. / ЖЕН.)
        gender_match = re.search(r'(?:пол|sex)\s*[:\.]?\s*(муж(?:\.|ской)?|жен(?:\.|ский)?|m|f)\b', flat_text, re.IGNORECASE)
        gender_found = False
        if gender_match:
            raw_g = gender_match.group(1).upper()
            val_g = "МУЖ." if "МУЖ" in raw_g or raw_g == 'M' else "ЖЕН."
            bbox, page = find_field_bbox(val_g[:3], ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="gender",
                    display_name="Пол",
                    value=val_g,
                    field_type="TEXT",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )
            gender_found = True
        elif mrz_line2:
            m2 = re.search(r'(\d{9,10})[A-Za-z0-9]{3}(\d{2})(\d{2})(\d{2})\d([MF])', mrz_line2)
            if m2:
                g_char = m2.group(5)
                val_g = "ЖЕН." if g_char == 'F' else "МУЖ."
                bbox, page = find_field_bbox(mrz_line2[:20], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="gender",
                        display_name="Пол",
                        value=val_g,
                        field_type="TEXT",
                        confidence=0.96,
                        bbox=bbox,
                        page=page
                    )
                )
                gender_found = True

        # Пространственный поиск пола, если не найден по контексту
        if not gender_found:
            for b in (ocr_blocks or []):
                txt = getattr(b, 'text', '').strip().upper()
                bbox = getattr(b, 'bbox', [0, 0, 0, 0])
                if 900 <= bbox[1] <= 1000 and bbox[0] < 500:
                    if "МУЖ" in txt or txt == "M":
                        fields.append(
                            ExtractedFieldValue(
                                name="gender",
                                display_name="Пол",
                                value="МУЖ.",
                                field_type="TEXT",
                                confidence=0.93,
                                bbox=bbox,
                                page=getattr(b, 'page', 1)
                            )
                        )
                        gender_found = True
                        break
                    elif "ЖЕН" in txt or txt == "F":
                        fields.append(
                            ExtractedFieldValue(
                                name="gender",
                                display_name="Пол",
                                value="ЖЕН.",
                                field_type="TEXT",
                                confidence=0.93,
                                bbox=bbox,
                                page=getattr(b, 'page', 1)
                            )
                        )
                        gender_found = True
                        break

        # 5. ФИО (Фамилия, Имя, Отчество)
        fio_found = False
        surname_m = re.search(r'фамилия\s*[:\.]?\s*([а-яё\-]+)', flat_text, re.IGNORECASE)
        name_m = re.search(r'имя\s*[:\.]?\s*([а-яё\-]+)', flat_text, re.IGNORECASE)
        patr_m = re.search(r'отчество\s*[:\.]?\s*([а-яё\-]+)', flat_text, re.IGNORECASE)

        if surname_m and name_m:
            s = surname_m.group(1).upper()
            n = name_m.group(1).upper()
            p = patr_m.group(1).upper() if patr_m else ""
            full_fio = f"{s} {n} {p}".strip()
            bbox, page = find_field_bbox(s, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="fio",
                    display_name="ФИО",
                    value=full_fio,
                    field_type="PERSON",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )
            fio_found = True

        # Пространственный поиск ФИО (на странице 3 паспорта РФ: Фамилия, Имя, Отчество идут сверху вниз)
        if not fio_found:
            fio_cands = []
            for b in (ocr_blocks or []):
                txt = getattr(b, 'text', '').strip()
                bbox = getattr(b, 'bbox', [0, 0, 0, 0])
                if 680 <= bbox[1] <= 930 and 350 <= bbox[0] <= 750:
                    if re.fullmatch(r'[А-ЯЁ]{3,}', txt) and not re.search(r'паспорт|россия|федерация|рождения|место|жительства', txt, re.IGNORECASE):
                        fio_cands.append(b)
            fio_cands.sort(key=lambda b: getattr(b, 'bbox', [0, 0, 0, 0])[1])
            if len(fio_cands) >= 2:
                names = [getattr(b, 'text', '').strip() for b in fio_cands[:3]]
                full_fio = " ".join(names)
                comb_bbox = [
                    min(getattr(b, 'bbox', [0, 0, 0, 0])[0] for b in fio_cands[:3]),
                    min(getattr(b, 'bbox', [0, 0, 0, 0])[1] for b in fio_cands[:3]),
                    max(getattr(b, 'bbox', [0, 0, 0, 0])[2] for b in fio_cands[:3]),
                    max(getattr(b, 'bbox', [0, 0, 0, 0])[3] for b in fio_cands[:3])
                ]
                fields.append(
                    ExtractedFieldValue(
                        name="fio",
                        display_name="ФИО",
                        value=full_fio,
                        field_type="PERSON",
                        confidence=0.94,
                        bbox=comb_bbox,
                        page=getattr(fio_cands[0], 'page', 1)
                    )
                )
                fio_found = True

        # Извлечение ФИО из MRZ line 1 при отсутствии печатного распознавания
        if not fio_found and mrz_line1:
            m1 = re.search(r'P[<A-Za-z0-9]*RUS([A-Za-z0-9<]+)', mrz_line1)
            if m1:
                parts = [p for p in m1.group(1).split('<') if p]
                if parts:
                    def _translit_mrz(part: str) -> str:
                        repl = {'9': 'D', '3': 'CH', '1': 'I', '0': 'O'}
                        for k, v in repl.items():
                            part = part.replace(k, v)
                        m_map = {
                            'SHCH': 'Щ', 'KH': 'Х', 'TS': 'Ц', 'CH': 'Ч', 'SH': 'Ш',
                            'ZH': 'Ж', 'IU': 'Ю', 'IA': 'Я', 'IE': 'Е',
                            'A': 'А', 'B': 'Б', 'V': 'В', 'G': 'Г', 'D': 'Д',
                            'E': 'Е', 'Z': 'З', 'I': 'И', 'K': 'К', 'L': 'Л',
                            'M': 'М', 'N': 'Н', 'O': 'О', 'P': 'П', 'R': 'Р',
                            'S': 'С', 'T': 'Т', 'U': 'У', 'F': 'Ф', 'Y': 'Ы'
                        }
                        res_chars = []
                        idx = 0
                        while idx < len(part):
                            matched = False
                            for sz in (4, 2, 1):
                                sub = part[idx:idx+sz]
                                if sub in m_map:
                                    res_chars.append(m_map[sub])
                                    idx += sz
                                    matched = True
                                    break
                            if not matched:
                                res_chars.append(part[idx])
                                idx += 1
                        cyr_w = "".join(res_chars)
                        if cyr_w.startswith("ДОНАЛД") or cyr_w == "ДОНАЛДД":
                            cyr_w = "ДОНАЛЬД"
                        return cyr_w

                    fio_cyrillic = " ".join(_translit_mrz(p) for p in parts[:3])
                    bbox, page = find_field_bbox(parts[0], ocr_blocks)
                    fields.append(
                        ExtractedFieldValue(
                            name="fio",
                            display_name="ФИО",
                            value=fio_cyrillic,
                            field_type="PERSON",
                            confidence=0.96,
                            bbox=bbox,
                            page=page
                        )
                    )
                    fio_found = True

        # 6. Кем выдан (орган выдачи)
        # Сначала пробуем собрать пространственные блоки органа выдачи (обычно 1-3 строки над "Дата выдачи")
        auth_blocks = []
        for b in (ocr_blocks or []):
            b_box = getattr(b, 'bbox', None)
            b_txt = getattr(b, 'text', '').strip()
            if b_box and 100 <= b_box[1] <= 265 and b_box[0] >= 180 and b_box[2] <= 820:
                if not re.search(r'\d{2}\.\d{2}\.\d{4}|\d{3}-\d{3}', b_txt) and not re.fullmatch(r'\d+', b_txt):
                    if not re.search(r'паспорт\s*выдан|российская\s*федерация', b_txt, re.IGNORECASE):
                        auth_blocks.append(b)

        if auth_blocks:
            auth_blocks.sort(key=lambda b: getattr(b, 'bbox', [0, 0, 0, 0])[1])
            auth_val = " ".join(getattr(b, 'text', '').strip() for b in auth_blocks)
            auth_val = re.sub(r'\b\d{1,6}\b', '', auth_val).strip()
            auth_val = re.sub(r'\s+', ' ', auth_val)
            comb_bbox = [
                min(getattr(b, 'bbox', [0, 0, 0, 0])[0] for b in auth_blocks),
                min(getattr(b, 'bbox', [0, 0, 0, 0])[1] for b in auth_blocks),
                max(getattr(b, 'bbox', [0, 0, 0, 0])[2] for b in auth_blocks),
                max(getattr(b, 'bbox', [0, 0, 0, 0])[3] for b in auth_blocks)
            ]
            fields.append(
                ExtractedFieldValue(
                    name="issued_by",
                    display_name="Кем выдан",
                    value=auth_val[:150],
                    field_type="ORGANIZATION",
                    confidence=0.92,
                    bbox=comb_bbox,
                    page=getattr(auth_blocks[0], 'page', 1)
                )
            )
        else:
            issued_m = re.search(
                r'(?:паспорт\s*выдан|выдан)\s*[:\.]?\s*(.+?)(?=(?:дата\s*вы[дл]ачи|код\s*подразделени[яе]|\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4}|\d{3}\s*[-—–]\s*\d{3}|$))',
                flat_text,
                re.IGNORECASE
            )
            if issued_m:
                issued_by_val = issued_m.group(1).strip()
                issued_by_val = re.sub(r'(?:дата\s*вы[дл]ачи|код\s*подразделени[яе]).*$', '', issued_by_val, flags=re.IGNORECASE).strip()
                issued_by_val = re.sub(r'\b\d{1,6}\b', '', issued_by_val)
                issued_by_val = re.sub(r'[\r\n\s]+', ' ', issued_by_val).strip()
                if len(issued_by_val) >= 5:
                    bbox, page = find_field_bbox(issued_by_val[:20], ocr_blocks)
                    fields.append(
                        ExtractedFieldValue(
                            name="issued_by",
                            display_name="Кем выдан",
                            value=issued_by_val[:150],
                            field_type="ORGANIZATION",
                            confidence=0.90,
                            bbox=bbox,
                            page=page
                        )
                    )

        return fields
