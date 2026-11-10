"""
Извлечение полей карточки документа из текста: номер, дата, контрагенты, ИНН, сумма, срок действия.
Поля нужны для фильтров поиска, колонок реестра и сводок ассистента.
"""

from __future__ import annotations

import re
from typing import List, Optional

from app.checks.blocks import parse_blocks
from app.checks.rules import AMOUNT_WITH_WORDS, SP, _iter_dates, inn_valid

ORG = re.compile(r"\b(ООО|АО|ПАО|ЗАО|ОАО|НКО|ФГУП|МУП|ГУП)" + SP + r"*«([^»]{2,80})»")
IP = re.compile(r"\bИП" + SP + r"+([А-ЯЁ][а-яё]+(?:" + SP + r"+[А-ЯЁ]\." + SP + r"*[А-ЯЁ]\.|" + SP + r"+[А-ЯЁ][а-яё]+){1,2})")
NUMBER = re.compile(r"№" + SP + r"*([A-Za-zА-Яа-яЁё0-9][\w\-/.]*[\wА-Яа-я])")
AMOUNT_NEAR = re.compile(r"(?:сумм|стоимост|цен|итог|бюджет)[а-яё]*[^.;]{0,60}?(\d{1,3}(?:" + SP + r"\d{3})+|\d{4,})(?:[,.](\d{2}))?" + SP + r"*(?:руб|₽|\()", re.IGNORECASE)
# слова, которыми сумму пишут прописью: «1 250 000 (один миллион двести пятьдесят тысяч) рублей»
NUMBER_WORDS = re.compile(r"(?<![а-яё])(?:ноль|один|одна|одной|две|два|двух|три|трех|трёх|четыр|пят|шест|семь|сем[иь]|восем|девят|десят|сорок|сто|двести|триста|тысяч|миллион|миллиард)", re.IGNORECASE)
MONEY_MARK = re.compile(r"руб|₽|коп", re.IGNORECASE)
UNTIL = re.compile(r"(?:действует|действия|срок[а-яё]*)[^.;]{0,50}?до" + SP + r"+(.{6,25})", re.IGNORECASE)


def _iso(d) -> Optional[str]:
    return d.isoformat() if d else None


def extract_fields(html: str) -> dict:
    blocks, _ = parse_blocks(html)
    texts = [b.text for b in blocks]
    head = texts[:5]
    full = "\n".join(texts)

    title = next((b.text.strip() for b in blocks if b.tag in ("h1", "h2") and b.text.strip()), texts[0].strip() if texts else "")

    number = None
    for t in head:
        m = NUMBER.search(t)
        if m:
            number = m.group(1)
            break

    doc_date = None
    for t in head:
        d = next((x[0] for x in _iter_dates(t) if x[0]), None)
        if d:
            doc_date = d
            break

    parties: List[str] = []
    for m in ORG.finditer(full):
        name = f"{m.group(1)} «{m.group(2).strip()}»"
        if name not in parties:
            parties.append(name)
    for m in IP.finditer(full):
        name = "ИП " + re.sub(SP + "+", " ", m.group(1))
        if name not in parties:
            parties.append(name)

    inns = []
    for m in re.finditer(r"ИНН(?:" + SP + r"*/" + SP + r"*КПП)?" + SP + r"*:?" + SP + r"*(\d{10}|\d{12})\b", full):
        if m.group(1) not in [i["value"] for i in inns]:
            inns.append({"value": m.group(1), "valid": inn_valid(m.group(1))})

    amount = None
    # «число (текст в скобках)» — сумма, только если в скобках число прописью и рядом стоят рубли:
    # иначе суммой становились «2 (два) экземпляра» и «4 (четырёх) комнатной квартире»
    m = next((x for x in AMOUNT_WITH_WORDS.finditer(full)
              if NUMBER_WORDS.search(x.group(2)) and MONEY_MARK.search(full[x.start():x.end() + 25])), None)
    if m:
        amount = float(re.sub(r"\D", "", m.group(1)))
    else:
        m = AMOUNT_NEAR.search(full)
        if m:
            amount = float(re.sub(r"\D", "", m.group(1)) + ("." + m.group(2) if m.group(2) else ""))

    valid_until = None
    for m in UNTIL.finditer(full):
        d = next((x[0] for x in _iter_dates(m.group(1)) if x[0]), None)
        if d:
            valid_until = d
            break

    return {
        "title": title[:300],
        "number": number,
        "date": _iso(doc_date),
        "counterparties": parties[:6],
        "inns": inns[:6],
        "amount": amount,
        "validUntil": _iso(valid_until),
    }
