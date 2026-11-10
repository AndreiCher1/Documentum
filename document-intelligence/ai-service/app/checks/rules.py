"""
Правила проверки текста документа.

Каждое правило получает контекст (блоки, таблицы, тип документа) и добавляет находки.
Находка привязана к блоку и диапазону символов в его тексте; если у неё есть replacement,
редактор показывает правку «было → стало», иначе — замечание без автоисправления.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Callable, Dict, List, Optional

from app.checks.blocks import Block, Table
from app.checks.numbers_ru import find_number_words, number_to_words

NBSP = " "
SP = r"[  ]"


@dataclass
class Finding:
    rule: str
    severity: str            # critical | warning | info
    category: str
    title: str
    why: str
    block: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None
    quote: str = ""
    replacement: Optional[str] = None
    where: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Context:
    blocks: List[Block]
    tables: List[Table]
    document_type: str = ""
    findings: List[Finding] = field(default_factory=list)
    defined_points: set = field(default_factory=set)

    def add(self, rule, severity, category, title, why, block: Optional[Block] = None, start=None, end=None, replacement=None):
        quote = block.text[start:end] if block is not None and start is not None else ""
        self.findings.append(Finding(rule, severity, category, title, why, block.index if block else None,
                                     start, end, quote, replacement))


RULES: List[Callable[[Context], None]] = []


def rule(fn):
    RULES.append(fn)
    return fn


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Реквизиты
# ---------------------------------------------------------------------------

def inn_valid(v: str) -> bool:
    if not re.fullmatch(r"\d{10}|\d{12}", v):
        return False
    d = [int(c) for c in v]
    chk = lambda w: sum(a * b for a, b in zip(w, d)) % 11 % 10
    if len(d) == 10:
        return chk([2, 4, 10, 3, 5, 9, 4, 6, 8]) == d[9]
    return chk([7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == d[10] and chk([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == d[11]


def ogrn_valid(v: str) -> bool:
    if len(v) == 13:
        return int(v[:12]) % 11 % 10 == int(v[12])
    if len(v) == 15:
        return int(v[:14]) % 13 % 10 == int(v[14])
    return False


def account_valid(account: str, bik: str) -> bool:
    """Ключ расчётного счёта: последние 3 цифры БИК + 20 цифр счёта, веса 7-1-3, сумма кратна 10."""
    s = bik[-3:] + account
    weights = [7, 1, 3] * 8
    return sum(int(c) * w for c, w in zip(s, weights)) % 10 == 0


@rule
def requisites(ctx: Context):
    all_text = " ".join(b.text for b in ctx.blocks)
    banks = re.findall(r"БИК" + SP + r"*:?" + SP + r"*(\d{9})\b", all_text)
    for b in ctx.blocks:
        t = b.text
        for m in re.finditer(r"ИНН(?:" + SP + r"*/" + SP + r"*КПП)?" + SP + r"*:?" + SP + r"*(\d{9,13})\b", t):
            v = m.group(1)
            s, e = m.span(1)
            if len(v) not in (10, 12):
                ctx.add("inn", "critical", "Реквизиты", "ИНН неверной длины",
                        f"ИНН организации — 10 цифр, ИП и физического лица — 12. Здесь {len(v)}.", b, s, e)
            elif not inn_valid(v):
                ctx.add("inn", "critical", "Реквизиты", "Неверный ИНН",
                        "Контрольная сумма ИНН не сходится — в номере ошибка (часто переставлены соседние цифры). Сверьте с выпиской ЕГРЮЛ или счётом.", b, s, e)
        for m in re.finditer(r"КПП" + SP + r"*:?" + SP + r"*(\d+)\b", t):
            if len(m.group(1)) != 9:
                ctx.add("kpp", "warning", "Реквизиты", "КПП неверной длины", f"КПП состоит из 9 цифр, здесь {len(m.group(1))}.", b, *m.span(1))
        for m in re.finditer(r"ОГРН(ИП)?" + SP + r"*:?" + SP + r"*(\d{11,16})\b", t):
            v = m.group(2)
            if not ogrn_valid(v):
                ctx.add("ogrn", "critical", "Реквизиты", "Неверный ОГРН" if len(v) in (13, 15) else "ОГРН неверной длины",
                        "ОГРН — 13 цифр, ОГРНИП — 15; последняя цифра контрольная и здесь не сходится.", b, *m.span(2))
        for m in re.finditer(r"БИК" + SP + r"*:?" + SP + r"*(\d+)\b", t):
            v = m.group(1)
            if len(v) != 9 or not v.startswith("04"):
                ctx.add("bik", "critical", "Реквизиты", "Неверный БИК", "БИК российского банка — 9 цифр и начинается с 04.", b, *m.span(1))
        for m in re.finditer(r"(?:р/с|р\.?" + SP + r"?с\.|расч[её]тный" + SP + r"+сч[её]т)" + SP + r"*(?:№" + SP + r"*)?:?" + SP + r"*(\d{15,25})\b", t, re.IGNORECASE):
            v = m.group(1)
            local_bik = re.search(r"БИК" + SP + r"*:?" + SP + r"*(\d{9})\b", t)
            bik = local_bik.group(1) if local_bik else (banks[0] if len(banks) == 1 else None)
            if len(v) != 20:
                ctx.add("account", "critical", "Реквизиты", "Расчётный счёт неверной длины", f"Расчётный счёт — 20 цифр, здесь {len(v)}.", b, *m.span(1))
            elif bik and not account_valid(v, bik):
                ctx.add("account", "critical", "Реквизиты", "Расчётный счёт не соответствует БИК",
                        f"Контрольный ключ счёта не сходится с БИК {bik}: ошибка в номере счёта или БИК.", b, *m.span(1))


# ---------------------------------------------------------------------------
# Даты
# ---------------------------------------------------------------------------

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
DATE_WORDS = re.compile(r"(?<!\d)(\d{1,2})" + SP + r"+(" + "|".join(MONTHS) + r")" + SP + r"+(\d{4})", re.IGNORECASE)
DATE_NUM = re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})\.(\d{4})(?![\d.]\d)")


def _iter_dates(text: str):
    """(date|None, day, month, year, span дня, span всей даты)"""
    for m in DATE_WORDS.finditer(text):
        d, mon, y = int(m.group(1)), MONTHS.index(m.group(2).lower()) + 1, int(m.group(3))
        yield _safe_date(y, mon, d), d, mon, y, m.span(1), m.span()
    for m in DATE_NUM.finditer(text):
        d, mon, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        yield _safe_date(y, mon, d), d, mon, y, m.span(1), m.span()


def _safe_date(y, m, d) -> Optional[date]:
    try:
        return date(y, m, d)
    except ValueError:
        return None


@rule
def dates(ctx: Context):
    for b in ctx.blocks:
        for dt, d, mon, y, dspan, span in _iter_dates(b.text):
            if dt is not None or not (1900 <= y <= 2100):
                continue
            if 1 <= mon <= 12:
                last = calendar.monthrange(y, mon)[1]
                ctx.add("date", "critical", "Реквизиты", "Несуществующая дата",
                        f"В этом месяце {last} {'день' if last == 31 else 'дней'}: {d}-го числа нет. Срок с такой датой можно оспорить.",
                        b, dspan[0], dspan[1], str(last).zfill(len(b.text[dspan[0]:dspan[1]])))
            else:
                ctx.add("date", "critical", "Реквизиты", "Несуществующая дата", f"Месяца с номером {mon} нет.", b, span[0], span[1])
        # период «с … по …» в обратном порядке
        for m in re.finditer(r"\bс" + SP + r"+(.{6,25}?)" + SP + r"+(?:г\." + SP + r"*)?по" + SP + r"+(.{6,25})", b.text):
            a = next(_iter_dates(m.group(1)), None)
            z = next(_iter_dates(m.group(2)), None)
            if a and z and a[0] and z[0] and z[0] < a[0]:
                ctx.add("period", "critical", "Противоречия", "Окончание периода раньше начала",
                        f"Период «с {a[0]:%d.%m.%Y} по {z[0]:%d.%m.%Y}»: дата окончания раньше даты начала.", b, *m.span())


# ---------------------------------------------------------------------------
# Суммы
# ---------------------------------------------------------------------------

AMOUNT_WITH_WORDS = re.compile(r"(?<![\d.,])(\d{1,3}(?:" + SP + r"\d{3})+|\d+)(?:[,.]\d{1,2})?" + SP + r"*(?:руб(?:\.|л[а-я]*)?" + SP + r"*)?\(([^()]{3,250})\)")


@rule
def amount_in_words(ctx: Context):
    for b in ctx.blocks:
        for m in AMOUNT_WITH_WORDS.finditer(b.text):
            digits = int(_digits(m.group(1)))
            found = find_number_words(m.group(2))
            if not found:
                continue
            value, ws, we = found
            if value == digits:
                continue
            start, end = m.start(2) + ws, m.start(2) + we
            original = b.text[start:end]
            correct = number_to_words(digits)
            if original[:1].isupper():
                correct = correct[:1].upper() + correct[1:]
            ctx.add("amount_words", "critical", "Противоречия", "Сумма цифрами не совпадает с суммой прописью",
                    f"Цифрами указано {_fmt_int(digits)}, прописью — {_fmt_int(value)}. При споре суд опирается на сумму прописью; разница — {_fmt_int(abs(digits - value))}.",
                    b, start, end, correct)


def _num(text: str) -> Optional[float]:
    t = text.replace(NBSP, " ").strip()
    m = re.fullmatch(r"-?\d{1,3}(?: \d{3})+(?:[,.]\d+)?|-?\d+(?:[,.]\d+)?", t.replace(" ₽", "").replace("руб.", "").strip())
    if not m:
        return None
    return float(m.group().replace(" ", "").replace(",", "."))


def _fmt_like(value: float, sample: str) -> str:
    decimals = re.search(r"[,.](\d+)\s*$", sample.strip())
    if decimals:
        n = len(decimals.group(1))
        s = f"{value:,.{n}f}".replace(",", " ").replace(".", ",")
    else:
        s = f"{round(value):,}".replace(",", " ")
    return s if " " in sample.strip() or abs(value) < 1000 else s.replace(" ", "")


@rule
def table_totals(ctx: Context):
    for ti, table in enumerate(ctx.tables):
        if len(table.rows) < 3:
            continue
        cells = [[ctx.blocks[i] for i in row] for row in table.rows]
        header = [c.text.lower() for c in cells[0]]
        col = lambda *keys: next((k for k, h in enumerate(header) if any(x in h for x in keys)), None)
        qty, price, total_col = col("кол"), col("цена"), col("сумм", "стоимост")

        def value(i, k):
            """Значение ячейки; в столбце «Сумма» — уже исправленное (кол-во × цена), чтобы правки не спорили друг с другом."""
            row = cells[i]
            if k == total_col and None not in (qty, price) and max(qty, price) < len(row):
                q, p = _num(row[qty].text), _num(row[price].text)
                if q is not None and p is not None:
                    return q * p
            return _num(row[k].text) if k < len(row) else None

        body_end = len(cells)
        for r, row in enumerate(cells[1:], start=1):
            first = " ".join(c.text.lower() for c in row[:2])
            if re.search(r"итог|всего", first):
                body_end = r
                # итоговая строка: сравнить каждый числовой столбец с суммой строк выше
                for k, cell in enumerate(row):
                    v = _num(cell.text)
                    if v is None or k == qty or k == price:
                        continue
                    vals = [value(i, k) for i in range(1, r)]
                    vals = [x for x in vals if x is not None]
                    if len(vals) >= 2 and abs(sum(vals) - v) > 0.009:
                        txt = cell.text
                        s = len(txt) - len(txt.lstrip())
                        ctx.add("table_total", "critical", "Противоречия", "Итог не равен сумме строк",
                                f"Сумма строк таблицы — {_fmt_like(sum(vals), txt)}, а в строке «Итого» указано {txt.strip()}.",
                                cell, s, len(txt.rstrip()), _fmt_like(sum(vals), txt))
                break
        if None in (qty, price, total_col):
            continue
        for row in cells[1:body_end]:
            if max(qty, price, total_col) >= len(row):
                continue
            q, p, s_ = _num(row[qty].text), _num(row[price].text), _num(row[total_col].text)
            if None in (q, p, s_) or abs(q * p - s_) <= 0.009:
                continue
            cell = row[total_col]
            txt = cell.text
            s = len(txt) - len(txt.lstrip())
            ctx.add("row_math", "critical", "Противоречия", "Количество × цена не равно сумме",
                    f"{row[qty].text.strip()} × {row[price].text.strip()} = {_fmt_like(q * p, txt)}, а в таблице {txt.strip()}.",
                    cell, s, len(txt.rstrip()), _fmt_like(q * p, txt))


# ---------------------------------------------------------------------------
# Нумерация и ссылки
# ---------------------------------------------------------------------------

POINT = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2})+)\.?(?=\s)")
SECTION = re.compile(r"^\s*(\d{1,2})\.(?=\s)")


@rule
def numbering(ctx: Context):
    last: Dict[str, int] = {}
    last_section = 0
    for b in ctx.blocks:
        if b.table is not None:
            continue
        sec = SECTION.match(b.text) if b.tag in ("h1", "h2", "h3") or b.text.strip().isupper() else None
        if sec:
            n = int(sec.group(1))
            ctx.defined_points.add(str(n))
            if last_section and n != last_section + 1:
                exp = last_section + 1
                ctx.add("numbering", "warning", "Оформление", "Сбита нумерация разделов",
                        f"После раздела {last_section} идёт раздел {n}." + (" Номер повторяется." if n == last_section else ""),
                        b, *sec.span(1), str(exp))
            last_section = n
            continue
        m = POINT.match(b.text)
        if not m:
            continue
        num = m.group(1)
        parent, _, child = num.rpartition(".")
        n = int(child)
        ctx.defined_points.add(num)
        ctx.defined_points.add(parent)
        prev = last.get(parent, 0)
        if (prev and n != prev + 1) or (not prev and n not in (1,)):
            exp = prev + 1
            ctx.add("numbering", "warning", "Оформление", "Сбита нумерация пунктов",
                    f"После п. {parent}.{prev} идёт п. {num}." if prev else f"Раздел {parent} начинается с п. {num}, а не с {parent}.1.",
                    b, *m.span(1), f"{parent}.{exp}")
        last[parent] = n


@rule
def references(ctx: Context):
    # Проверяем ссылки только на тот уровень нумерации, который в документе есть:
    # если своих подпунктов «3.1» нет, ссылка «п. 3.1», скорее всего, ведёт в другой документ
    has_points = sum(1 for p in ctx.defined_points if "." in p) >= 3
    has_sections = sum(1 for p in ctx.defined_points if "." not in p) >= 3
    if not (has_points or has_sections):
        return
    ref = re.compile(r"\b(?:пп?\.|пункт[а-я]*|раздел[а-я]*)" + SP + r"*(\d{1,2}(?:\.\d{1,2})*)(?![\d.]\d)", re.IGNORECASE)
    for b in ctx.blocks:
        head = POINT.match(b.text)
        for m in ref.finditer(b.text):
            num = m.group(1).rstrip(".")
            level_known = has_points if "." in num else has_sections
            if not level_known or num in ctx.defined_points or (head and m.start() < head.end()):
                continue
            # «п. 6.1 договора № 33/П» — ссылка на другой документ
            if re.match(SP + r"*(?:договора|приказа|регламента|положения|закона|ГК|НК|ТК|статьи)\b", b.text[m.end():m.end() + 14]) and "Договора" not in b.text[m.end():m.end() + 10]:
                continue
            ctx.add("reference", "warning", "Шаблон", "Ссылка на несуществующий пункт",
                    f"В документе нет пункта {num}. Исправьте ссылку или добавьте пункт.", b, *m.span())


# ---------------------------------------------------------------------------
# Шаблон документа
# ---------------------------------------------------------------------------

REQUIRED = {
    "CONTRACT": [("Предмет договора", ["предмет"]), ("Цена и порядок расчётов", ["цен", "стоимост", "расч", "оплат", "плат"]),
                 ("Срок действия", ["срок", "действует до", "действия договора"]), ("Ответственность сторон", ["ответственност"]),
                 ("Разрешение споров", ["спор"]), ("Реквизиты и подписи сторон", ["реквизит", "подпис", "адреса"])],
    "SUPPLEMENTARY_AGREEMENT": [("Ссылка на основной договор", ["к договору", "договор №", "договору №"])],
    "TECH_SPEC": [("Цели и назначение", ["цел", "назначени"]), ("Требования", ["требован"]), ("Сроки выполнения", ["срок"]),
                  ("Порядок приёмки", ["приёмк", "приемк", "сдач"]), ("Стоимость", ["стоимост", "цен", "бюджет"])],
    "REGULATION": [("Общие положения", ["общие положения"]), ("Ответственность", ["ответственн"])],
}


@rule
def template(ctx: Context):
    req = REQUIRED.get(ctx.document_type)
    if not req or not ctx.blocks:
        return
    heads = [b.text.lower() for b in ctx.blocks if b.tag in ("h1", "h2", "h3") or (b.text.strip().isupper() and len(b.text) < 120)]
    pool = " ".join(heads) if len(heads) >= 3 else " ".join(b.text.lower() for b in ctx.blocks)
    missing = [name for name, keys in req if not any(k in pool for k in keys)]
    for name in missing:
        ctx.add("template", "warning", "Шаблон", f"Нет раздела «{name}»",
                "Для документа этого типа раздел обязателен по шаблону. Его отсутствие — частая причина споров и возвратов на доработку.")


@rule
def placeholders(ctx: Context):
    pat = re.compile(r"_{3,}|«" + SP + r"*_+" + SP + r"*»|\[" + SP + r"*\]|\b(?:ХХ|XX)\.(?:ХХ|XX)\.(?:ХХХХ|XXXX)\b")
    for b in ctx.blocks:
        for m in pat.finditer(b.text):
            ctx.add("placeholder", "warning", "Шаблон", "Не заполнено поле",
                    "В документе осталось пустое место для заполнения.", b, *m.span())


# ---------------------------------------------------------------------------
# Оформление и орфография
# ---------------------------------------------------------------------------

@rule
def spacing_and_quotes(ctx: Context):
    uses_guillemets = any("«" in b.text for b in ctx.blocks)
    for b in ctx.blocks:
        for m in re.finditer(r"(?<=[^\s ])(  |  )(?=[^\s ])", b.text):
            ctx.add("double_space", "info", "Оформление", "Двойной пробел", "Между словами два пробела.", b, *m.span(), " ")
        if uses_guillemets:
            for m in re.finditer(r'"([^"]{1,80})"', b.text):
                ctx.add("quotes", "info", "Оформление", "Разные кавычки",
                        "В документе используются кавычки-«ёлочки», а здесь — прямые.", b, *m.span(), f"«{m.group(1)}»")


HOMOGLYPHS = {"A": "А", "a": "а", "B": "В", "C": "С", "c": "с", "E": "Е", "e": "е", "H": "Н", "K": "К", "k": "к",
              "M": "М", "O": "О", "o": "о", "P": "Р", "p": "р", "T": "Т", "X": "Х", "x": "х", "y": "у"}

COMMON_ERRORS = [
    (r"\bсогласно" + SP + r"+договора\b", "согласно договору", "После «согласно» — дательный падеж: «согласно договору»."),
    (r"\bсогласно" + SP + r"+приказа\b", "согласно приказу", "После «согласно» — дательный падеж: «согласно приказу»."),
    (r"\bсогласно" + SP + r"+графика\b", "согласно графику", "После «согласно» — дательный падеж."),
    (r"\bсогласно" + SP + r"+счета\b", "согласно счёту", "После «согласно» — дательный падеж."),
    (r"\bв" + SP + r"+течении" + SP + r"+(?=\d|\(|срока|период|года|месяц|недел|дн|рабоч|календарн)", "в течение ", "«В течение» (о времени) пишется с «е» на конце."),
    (r"\bпо" + SP + r"+истечение\b", "по истечении", "Правильно: «по истечении»."),
    (r"\bпо" + SP + r"+приезду\b", "по приезде", "Правильно: «по приезде»."),
    (r"\bпоставшик", "поставщик", "Опечатка: «поставщик»."),
    (r"\bобязуеться\b", "обязуется", "Опечатка: «обязуется»."),
    (r"\bросчет", "расчёт", "Опечатка: «расчёт»."),
    (r"\bпредоставлят\b", "предоставлять", "Опечатка."),
    (r"\bзаказчек", "заказчик", "Опечатка: «заказчик»."),
    (r"\bисполнитиль", "исполнитель", "Опечатка: «исполнитель»."),
    (r"\bдоговр\b", "договор", "Опечатка: «договор»."),
    (r"\bприложенние", "приложение", "Опечатка: «приложение»."),
]


def _keep_case(original: str, replacement: str) -> str:
    return replacement[:1].upper() + replacement[1:] if original[:1].isupper() else replacement


@rule
def spelling(ctx: Context):
    for b in ctx.blocks:
        t = b.text
        for pattern, fix, why in COMMON_ERRORS:
            for m in re.finditer(pattern, t, re.IGNORECASE):
                ctx.add("spelling", "info", "Орфография", "Ошибка в слове" if " " not in fix.strip() else "Ошибка в выражении",
                        why, b, *m.span(), _keep_case(m.group(), fix))
        # латинские буквы внутри русских слов (частая ошибка копирования и распознавания)
        for m in re.finditer(r"\b[А-Яа-яЁёA-Za-z]{3,}\b", t):
            w = m.group()
            cyr = sum(1 for c in w if "а" <= c.lower() <= "я" or c in "ёЁ")
            lat = [c for c in w if c.isascii()]
            if cyr >= 2 and lat and all(c in HOMOGLYPHS for c in lat):
                ctx.add("homoglyph", "info", "Орфография", "Латинские буквы в русском слове",
                        f"В слове «{w}» есть латинские буквы ({', '.join(sorted(set(lat)))}) — поиск и проверка его не найдут.",
                        b, *m.span(), "".join(HOMOGLYPHS.get(c, c) for c in w))
        # повтор слова подряд
        for m in re.finditer(r"\b([А-Яа-яЁё]{2,})" + SP + r"+(\1)\b", t, re.IGNORECASE):
            ctx.add("repeat", "info", "Орфография", "Слово повторяется", f"Слово «{m.group(1)}» написано дважды подряд.",
                    b, m.start(), m.end(), m.group(1))
