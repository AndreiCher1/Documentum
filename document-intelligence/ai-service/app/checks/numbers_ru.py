"""Числа прописью по-русски: разбор («один миллион двести тысяч» → 1 200 000) и запись (1 250 000 → слова)."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_UNITS = {"ноль": 0, "один": 1, "одна": 1, "одно": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
          "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
          "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
          "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
          "восемьдесят": 80, "девяносто": 90, "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
          "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900}
_SCALES = {"тысяча": 10**3, "тысячи": 10**3, "тысяч": 10**3, "миллион": 10**6, "миллиона": 10**6, "миллионов": 10**6,
           "миллиард": 10**9, "миллиарда": 10**9, "миллиардов": 10**9}

_WORD = re.compile(r"[а-яё]+", re.IGNORECASE)


def find_number_words(text: str) -> Optional[Tuple[int, int, int]]:
    """
    Ищет в тексте первую непрерывную запись числа словами.
    Возвращает (значение, начало, конец) — позиции в исходной строке, или None.
    """
    words = [(m.group().lower().replace("ё", "е"), m.start(), m.end()) for m in _WORD.finditer(text)]
    start = end = None
    total = group = 0
    for w, s, e in words:
        if w in _UNITS:
            group += _UNITS[w]
        elif w in _SCALES:
            total += (group or 1) * _SCALES[w]
            group = 0
        else:
            if start is not None:
                break
            continue
        if start is None:
            start = s
        end = e
    if start is None:
        return None
    return total + group, start, end


_ONES_M = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_ONES_F = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать",
          "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _triad(n: int, feminine: bool) -> list:
    out = [_HUNDREDS[n // 100]]
    rest = n % 100
    if 10 <= rest < 20:
        out.append(_TEENS[rest - 10])
    else:
        out.append(_TENS[rest // 10])
        out.append((_ONES_F if feminine else _ONES_M)[rest % 10])
    return [w for w in out if w]


def number_to_words(n: int) -> str:
    if n == 0:
        return "ноль"
    parts = []
    for scale, forms, fem in ((10**9, ("миллиард", "миллиарда", "миллиардов"), False),
                              (10**6, ("миллион", "миллиона", "миллионов"), False),
                              (10**3, ("тысяча", "тысячи", "тысяч"), True)):
        chunk = (n // scale) % 1000
        if chunk:
            parts += _triad(chunk, fem) + [_plural(chunk, *forms)]
    parts += _triad(n % 1000, False)
    return " ".join(parts)
