"""
Экстрактор реквизитов Счёта на оплату (Invoice / УПД).

Извлекаемые ключевые поля:
- Номер счёта
- Дата счёта (в числовом или словесном формате)
- Поставщик (наименование)
- ИНН поставщика (10 или 12 цифр)
- КПП поставщика (9 цифр)
- Покупатель (наименование)
- ИНН покупателя
- Банк получателя
- БИК банка получателя (9 цифр, начинается с 04)
- Корреспондентский счёт (20 цифр, 30101...)
- Расчётный счёт (20 цифр, 40702... / 408...)
- Итоговая сумма к оплате
- Ставка и сумма НДС
"""

import re
from typing import Any, List, Optional
from app.extractor.base import BaseFieldExtractor, ExtractedFieldValue, find_field_bbox


MONTH_MAP = {
    'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04',
    'мая': '05', 'июня': '06', 'июля': '07', 'августа': '08',
    'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'
}


class InvoiceExtractor(BaseFieldExtractor):
    """Экстрактор структурированных данных из счетов на оплату."""

    def extract(self, text: str, ocr_blocks: Optional[List[Any]] = None) -> List[ExtractedFieldValue]:
        fields: List[ExtractedFieldValue] = []
        if not text:
            return fields

        flat_text = " ".join(text.split())

        # 1. Номер счёта
        num_m = re.search(r'(?:счет(?:\s*на\s*оплату)?|счёт)\s*(?:№|N|No|#)?\s*([A-Za-zА-Яа-я0-9\-\/]+)', flat_text, re.IGNORECASE)
        if num_m:
            inv_num = num_m.group(1).strip()
            if inv_num and not inv_num.lower().startswith(('от', 'на', 'в')):
                bbox, page = find_field_bbox(inv_num, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="invoice_number",
                        display_name="Номер счёта",
                        value=inv_num,
                        field_type="TEXT",
                        confidence=0.96,
                        bbox=bbox,
                        page=page
                    )
                )

        # 2. Дата счёта (цифровой или словесный формат)
        date_m = re.search(r'(?:от|дата)\s*[:\.]?\s*(\d{2}[\.\/]\d{2}[\.\/]\d{4})', flat_text, re.IGNORECASE)
        inv_date = None
        raw_date_token = None

        if date_m:
            inv_date = date_m.group(1).replace('/', '.')
            raw_date_token = date_m.group(1)
        else:
            # Словесный формат: "15" мая 2024 г. или 15 мая 2024 г.
            verb_date_m = re.search(r'[«"]?(\d{1,2})[»"]?\s+([а-яё]+)\s+(\d{4})\s*г\.?', flat_text, re.IGNORECASE)
            if verb_date_m:
                d = int(verb_date_m.group(1))
                m_str = verb_date_m.group(2).lower()
                y = verb_date_m.group(3)
                if m_str in MONTH_MAP:
                    inv_date = f"{d:02d}.{MONTH_MAP[m_str]}.{y}"
                    raw_date_token = verb_date_m.group(0)

        if inv_date:
            bbox, page = find_field_bbox(raw_date_token or inv_date, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="invoice_date",
                    display_name="Дата счёта",
                    value=inv_date,
                    field_type="DATE",
                    confidence=0.95,
                    bbox=bbox,
                    page=page
                )
            )

        # 3. ИНН и КПП поставщика и покупателя
        inns = list(re.finditer(r'\bинн(?:\s*\/|\s*[:\.]?)\s*(\d{10}|\d{12})\b', flat_text, re.IGNORECASE))
        if inns:
            seller_inn = inns[0].group(1)
            bbox, page = find_field_bbox(seller_inn, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="inn",
                    display_name="ИНН поставщика",
                    value=seller_inn,
                    field_type="INN",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )
            if len(inns) >= 2:
                buyer_inn = inns[1].group(1)
                bbox2, page2 = find_field_bbox(buyer_inn, ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="buyer_inn",
                        display_name="ИНН покупателя",
                        value=buyer_inn,
                        field_type="INN",
                        confidence=0.98,
                        bbox=bbox2,
                        page=page2
                    )
                )

        # 4. КПП
        kpps = list(re.finditer(r'\bкпп\s*[:\.]?\s*(\d{9})\b', flat_text, re.IGNORECASE))
        if kpps:
            kpp_val = kpps[0].group(1)
            bbox, page = find_field_bbox(kpp_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="kpp",
                    display_name="КПП поставщика",
                    value=kpp_val,
                    field_type="TEXT",
                    confidence=0.98,
                    bbox=bbox,
                    page=page
                )
            )

        # 5. Поставщик (наименование)
        seller_m = re.search(r'поставщик\s*[:\.]?\s*([«"А-Яа-яA-Za-z0-9\s\.\-]+?)(?=\s*инн|\s*кпп|\s*покупатель|\s*р\/с|$)', flat_text, re.IGNORECASE)
        if seller_m:
            s_name = seller_m.group(1).strip()
            if 3 <= len(s_name) <= 100:
                bbox, page = find_field_bbox(s_name[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="seller_name",
                        display_name="Поставщик",
                        value=s_name,
                        field_type="ORGANIZATION",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 6. Покупатель (наименование)
        buyer_m = re.search(r'покупатель\s*[:\.]?\s*([«"А-Яа-яA-Za-z0-9\s\.\-]+?)(?=\s*инн|\s*кпп|\s*грузополучатель|\s*основание|$)', flat_text, re.IGNORECASE)
        if buyer_m:
            b_name = buyer_m.group(1).strip()
            if 3 <= len(b_name) <= 100:
                bbox, page = find_field_bbox(b_name[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="buyer_name",
                        display_name="Покупатель",
                        value=b_name,
                        field_type="ORGANIZATION",
                        confidence=0.91,
                        bbox=bbox,
                        page=page
                    )
                )

        # 7. Банк получателя
        bank_m = re.search(r'(?:банк\s*получателя|наименование\s*банка)\s*[:\.]?\s*([«"А-Яа-яA-Za-z0-9\s\.\-]+?)(?=\s*бик|\s*р\/с|\s*к\/с|$)', flat_text, re.IGNORECASE)
        if bank_m:
            b_val = bank_m.group(1).strip()
            if len(b_val) >= 3:
                bbox, page = find_field_bbox(b_val[:15], ocr_blocks)
                fields.append(
                    ExtractedFieldValue(
                        name="bank_name",
                        display_name="Банк получателя",
                        value=b_val,
                        field_type="ORGANIZATION",
                        confidence=0.92,
                        bbox=bbox,
                        page=page
                    )
                )

        # 8. БИК банка (9 цифр, начинается с 04)
        bik_m = re.search(r'\bбик\s*[:\.]?\s*(04\d{7})\b', flat_text, re.IGNORECASE)
        if bik_m:
            bik_val = bik_m.group(1)
            bbox, page = find_field_bbox(bik_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="bik",
                    display_name="БИК Банка",
                    value=bik_val,
                    field_type="BIK",
                    confidence=0.97,
                    bbox=bbox,
                    page=page
                )
            )

        # 9. Расчётный счёт (20 цифр)
        acc_m = re.search(r'(?:р\/с|расчетный\s*счет|счет\s*получателя)\s*[:\.]?\s*(\d{20})\b', flat_text, re.IGNORECASE)
        if not acc_m:
            acc_m = re.search(r'\b(40702\d{15}|408\d{17})\b', flat_text)
        if acc_m:
            acc_val = acc_m.group(1)
            bbox, page = find_field_bbox(acc_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="settlement_account",
                    display_name="Расчётный счёт",
                    value=acc_val,
                    field_type="ACCOUNT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 10. Корреспондентский счёт (20 цифр, 30101...)
        corr_m = re.search(r'(?:к\/с|корр(?:еспондентский)?\s*счет)\s*[:\.]?\s*(30101\d{15})\b', flat_text, re.IGNORECASE)
        if corr_m:
            corr_val = corr_m.group(1)
            bbox, page = find_field_bbox(corr_val, ocr_blocks)
            fields.append(
                ExtractedFieldValue(
                    name="corr_account",
                    display_name="Корр. счёт",
                    value=corr_val,
                    field_type="ACCOUNT",
                    confidence=0.96,
                    bbox=bbox,
                    page=page
                )
            )

        # 11. Итоговая сумма к оплате
        amount_m = re.search(
            r'(?:всего\s*к\s*оплате|итого\s*к\s*оплате|итого|всего\s*наименований[^,]+на\s*сумму|сумма\s*к\s*оплате)\s*[:\.]?\s*([\d\s]{2,}(?:[\.,]\d{2})?)\s*(?:руб|р\.|\u20bd)?',
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
                        display_name="Сумма к оплате",
                        value=formatted_amt,
                        field_type="AMOUNT",
                        confidence=0.95,
                        bbox=bbox,
                        page=page
                    )
                )
            except ValueError:
                pass

        # 12. НДС
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
                    confidence=0.91,
                    bbox=bbox,
                    page=page
                )
            )

        return fields
