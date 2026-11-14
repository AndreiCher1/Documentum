"""
Орфография по словарю.

Словарь — русский словарь hunspell из LibreOffice (app/checks/dict/ru_RU.dic и .aff, автор А. И. Лебедев,
лицензия BSD — см. README_ru_RU.txt): 146 тысяч слов и правила окончаний, по которым из слова получаются его формы.
Библиотека hunspell не нужна: здесь разобраны только правила окончаний (SFX), других в этом словаре нет.

Слово считается известным, если оно есть в словаре или получается из словарного слова по правилу окончаний.
Опечаткой считается только слово, которого в словаре нет, НО рядом (одна замена, пропуск, лишняя буква или
перестановка соседних) есть известное слово. Незнакомые слова без близкой замены — фамилии, названия, термины —
не трогаем: ложные замечания раздражают сильнее, чем пропущенная опечатка.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

DICT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dict")
ALPHABET = "абвгдежзийклмнопрстуфхцчшщъыьэюя"


class Speller:
    def __init__(self, directory: str = DICT_DIR):
        self.directory = directory
        self.words: Dict[str, str] = {}                                   # слово → флаги правил
        self.rules: Dict[str, List[Tuple[str, str, Optional[re.Pattern]]]] = {}   # окончание → [(флаг, что вернуть, условие)]
        self.max_add = 0
        self.loaded = False
        self.failed: Optional[str] = None
        self._lock = threading.Lock()

    def available(self) -> bool:
        self._load()
        return self.loaded

    def _load(self) -> None:
        if self.loaded or self.failed:
            return
        with self._lock:
            if self.loaded or self.failed:
                return
            try:
                with open(os.path.join(self.directory, "ru_RU.aff"), encoding="utf-8") as f:
                    for line in f:
                        p = line.split()
                        if len(p) >= 5 and p[0] == "SFX" and p[3] != "Y" and p[3] != "N":
                            flag, strip, add, cond = p[1], p[2], p[3], p[4]
                            strip = "" if strip == "0" else strip.replace("ё", "е")
                            add = "" if add == "0" else add.replace("ё", "е")
                            rx = None if cond == "." else re.compile(cond.replace("ё", "е") + "$")
                            self.rules.setdefault(add, []).append((flag, strip, rx))
                            self.max_add = max(self.max_add, len(add))
                with open(os.path.join(self.directory, "ru_RU.dic"), encoding="utf-8") as f:
                    next(f)
                    for line in f:
                        word, _, flags = line.strip().partition("/")
                        if word:
                            word = word.lower().replace("ё", "е")
                            self.words[word] = self.words.get(word, "") + flags
                self.loaded = True
                logger.info("Орфографический словарь загружен: %s слов", len(self.words))
            except Exception as e:                     # словарь необязателен: без него остаётся проверка частых ошибок
                self.failed = f"Словарь не загрузился: {e}"
                logger.error(self.failed)

    def known(self, word: str) -> bool:
        """Есть ли слово (в любой форме) в словаре. Буквы «ё» и «е» не различаются."""
        self._load()
        w = word.lower().replace("ё", "е")
        if w in self.words:
            return True
        for n in range(0, min(self.max_add, len(w) - 1) + 1):
            add = w[len(w) - n:] if n else ""
            for flag, strip, rx in self.rules.get(add, ()):
                stem = (w[:len(w) - n] if n else w) + strip
                flags = self.words.get(stem)
                if flags and flag in flags and (rx is None or rx.search(stem)):
                    return True
        return False

    def suggest(self, word: str) -> Optional[str]:
        """Известное слово на расстоянии одной правки или None. Предпочитаем замену и перестановку (длина та же)."""
        w = word.lower().replace("ё", "е")
        # порядок — от самых частых опечаток к редким: перестановка соседних, пропущенная буква, не та буква, лишняя буква
        swaps = [w[:i] + w[i + 1] + w[i] + w[i + 2:] for i in range(len(w) - 1) if w[i] != w[i + 1]]
        inserts = [w[:i] + ch + w[i:] for i in range(len(w) + 1) for ch in ALPHABET]
        replaces = [w[:i] + ch + w[i + 1:] for i in range(len(w)) for ch in ALPHABET if ch != w[i]]
        deletes = [w[:i] + w[i + 1:] for i in range(len(w))]
        seen: Set[str] = set()
        for cand in swaps + inserts + replaces + deletes:
            if cand not in seen and len(cand) >= 4:
                seen.add(cand)
                if self.known(cand):
                    return cand
        return None


speller = Speller()


@lru_cache(maxsize=50000)
def check_word(word: str) -> Optional[str]:
    """None — слово в порядке (или судить не о чем); иначе — предложенная замена."""
    if speller.known(word):
        return None
    # составные слова через дефис и с приставками словарь знает плохо — не судим
    return speller.suggest(word)
