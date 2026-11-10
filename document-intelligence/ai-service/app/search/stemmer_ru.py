"""
Стеммер русского языка по алгоритму Snowball (Мартин Портер).

Отрезает окончания и суффиксы, чтобы разные формы слова давали одну основу:
«договор», «договора», «договору», «договорами» → «договор».
Реализация без внешних зависимостей — сервис работает офлайн.
"""

from __future__ import annotations

import re
from functools import lru_cache

VOWELS = "аеиоуыэюя"

PERFECTIVE_GERUND_1 = ("вшись", "вши", "в")                     # после а/я
PERFECTIVE_GERUND_2 = ("ившись", "ывшись", "ивши", "ывши", "ив", "ыв")
REFLEXIVE = ("ся", "сь")
ADJECTIVE = ("ими", "ыми", "его", "ого", "ему", "ому", "ее", "ие", "ые", "ое", "ей", "ий", "ый", "ой", "ем", "им",
             "ым", "ом", "их", "ых", "ую", "юю", "ая", "яя", "ою", "ею")
PARTICIPLE_1 = ("ем", "нн", "вш", "ющ", "щ")                       # после а/я
PARTICIPLE_2 = ("ивш", "ывш", "ующ")
VERB_1 = ("ете", "йте", "ешь", "нно", "ла", "на", "ли", "ем", "ло", "но", "ет", "ют", "ны", "ть", "й", "л", "н")  # после а/я
VERB_2 = ("уйте", "ейте", "ила", "ыла", "ена", "ите", "или", "ыли", "ило", "ыло", "ено", "ует", "уют", "ены", "ить",
          "ыть", "ишь", "ей", "уй", "ил", "ыл", "им", "ым", "ен", "ят", "ит", "ыт", "ую", "ю")
NOUN = ("иями", "ями", "ами", "ией", "иям", "ием", "иях", "ев", "ов", "ие", "ье", "еи", "ии", "ей", "ой", "ий", "ям",
        "ем", "ам", "ом", "ах", "ях", "ию", "ью", "ия", "ья", "а", "е", "и", "й", "о", "у", "ы", "ь", "ю", "я")
SUPERLATIVE = ("ейше", "ейш")
DERIVATIONAL = ("ость", "ост")


def _rv_r2(word: str):
    """Начало зон RV и R2 (индексы)."""
    rv = next((i + 1 for i, c in enumerate(word) if c in VOWELS), len(word))

    def r_after(start):
        for i in range(start + 1, len(word)):
            if word[i] not in VOWELS and word[i - 1] in VOWELS:
                return i + 1
        return len(word)

    r1 = r_after(0)
    r2 = r_after(r1) if r1 < len(word) else len(word)
    return rv, r2


def _strip(word: str, start: int, suffixes, need_a_ya: bool = False) -> str | None:
    """Отрезает самый длинный подходящий суффикс, целиком лежащий в зоне (с позиции start)."""
    for s in sorted(suffixes, key=len, reverse=True):
        if word.endswith(s) and len(word) - len(s) >= start:
            if need_a_ya:
                pos = len(word) - len(s) - 1
                if pos < start or word[pos] not in "ая":
                    continue
            return word[: len(word) - len(s)]
    return None


@lru_cache(maxsize=200_000)
def stem(word: str) -> str:
    w = word.lower().replace("ё", "е")
    if not re.fullmatch(r"[а-я]+", w) or len(w) < 3:
        return w
    rv, r2 = _rv_r2(w)

    # Шаг 1
    res = _strip(w, rv, PERFECTIVE_GERUND_1, True) or _strip(w, rv, PERFECTIVE_GERUND_2)
    if res is not None:
        w = res
    else:
        w = _strip(w, rv, REFLEXIVE) or w
        adj = _strip(w, rv, ADJECTIVE)
        if adj is not None:
            w = _strip(adj, rv, PARTICIPLE_1, True) or _strip(adj, rv, PARTICIPLE_2) or adj
        else:
            res = _strip(w, rv, VERB_1, True) or _strip(w, rv, VERB_2)
            if res is not None:
                w = res
            else:
                w = _strip(w, rv, NOUN) or w

    # Шаг 2
    if w.endswith("и") and len(w) - 1 >= rv:
        w = w[:-1]
    # Шаг 3
    res = _strip(w, r2, DERIVATIONAL)
    if res is not None:
        w = res
    # Шаг 4
    if w.endswith("нн") and len(w) - 1 >= rv:
        w = w[:-1]
    else:
        res = _strip(w, rv, SUPERLATIVE)
        if res is not None:
            w = res
            if w.endswith("нн"):
                w = w[:-1]
        elif w.endswith("ь") and len(w) - 1 >= rv:
            w = w[:-1]
    return w


TOKEN = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-/][A-Za-zА-Яа-яЁё0-9]+)*")


def tokens(text: str):
    """(основа, начало, конец) для каждого слова текста. Числа и номера сохраняются как есть."""
    for m in TOKEN.finditer(text):
        t = m.group()
        yield (stem(t) if re.search(r"[А-Яа-яЁё]", t) and not re.search(r"\d", t) else t.lower()), m.start(), m.end()
