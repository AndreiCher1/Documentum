"""
Смысловая проверка языковой моделью: противоречия между пунктами и рискованные условия.

Правила (rules.py) ловят то, что можно посчитать: реквизиты, суммы, даты. Здесь модель читает текст кусками
и ищет то, что требует понимания: «в п. 3.1 срок 10 дней, а в п. 5.2 — 30», «штраф без верхнего предела».
Каждая находка обязана ссылаться на фрагмент и содержать цитату; цитата ищется в тексте — так находка
получает точное место, а выдуманные моделью номера и цитаты отбрасываются.

Проверка небыстрая (десятки секунд на процессоре), поэтому запускается отдельной кнопкой, а не при каждой проверке.
Находки помечены ai=True: интерфейс показывает, что их нашла модель и что они требуют проверки человеком.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.checks.blocks import Block
from app.checks.rules import Context, Finding

logger = logging.getLogger(__name__)

CHUNK_CHARS = 3000        # текста в одном обращении к модели (контекст 4096 токенов, ответ ~20 с на процессоре)
MAX_CHUNKS = 4            # длинный документ проверяется не дальше этого объёма — иначе ждать минуты
MAX_PER_CHUNK = 5

SYSTEM = ("Ты — внимательный юрист, проверяющий деловой документ. Отвечай только по приведённому тексту, ничего не выдумывай. "
          "Цитаты переписывай из текста дословно.")
TASK = ("Найди в тексте:\n"
        "1) ПРОТИВОРЕЧИЕ — два места говорят разное об одном и том же (разные сроки, суммы, проценты, стороны, порядок действий);\n"
        "2) РИСК — условие, опасное или невыгодное для стороны: срок не указан, право только у одной стороны, "
        "штраф или неустойка без верхнего предела, автоматическое продление, расплывчатая ответственность, "
        "отказ без возврата денег.\n"
        "Противоречие — только когда в двух местах стоят разные числа или прямо противоположные условия. "
        "Обычные, нормальные условия не перечисляй. Лучше пропустить, чем придумать. Орфографию и оформление не оценивай.\n"
        "Каждую находку пиши отдельной строкой строго в виде:\n"
        "ТИП | номер фрагмента | дословная цитата из этого фрагмента (до 12 слов) | в чём проблема (одно предложение)\n"
        "Для противоречия укажи два номера через «и», цитату возьми из первого. "
        "Если находок нет, напиши одно слово: НЕТ.")
LINE = re.compile(r"^\W*(ПРОТИВОРЕЧИЕ|РИСК)\W*\|\s*\[?(\d+)\]?(?:\s*(?:и|,)\s*\[?(\d+)\]?)?\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$", re.IGNORECASE)


def _chunks(blocks: List[Block]) -> List[List[Block]]:
    out, cur, size = [], [], 0
    for b in blocks:
        text = b.text.strip()
        if len(text) < 3:
            continue
        if cur and size + len(text) > CHUNK_CHARS:
            out.append(cur)
            cur, size = [], 0
        cur.append(b)
        size += len(text)
    if cur:
        out.append(cur)
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("ё", "е").replace("Ё", "Е")).strip().lower()


def _locate(quote: str, block: Block) -> Optional[tuple]:
    """Место цитаты в абзаце. Модель может слегка изменить пробелы и кавычки — ищем и по началу цитаты."""
    quote = quote.strip(" «»\"'….")
    if len(quote) < 6:
        return None
    text = block.text
    low, q = text.lower().replace("ё", "е"), quote.lower().replace("ё", "е")
    i = low.find(q)
    if i >= 0:
        return i, i + len(q)
    words = q.split()
    for n in (6, 4, 3):                              # начало цитаты совпало — берём до конца предложения, но не длиннее цитаты
        if len(words) >= n:
            head = " ".join(words[:n])
            i = low.find(head)
            if i >= 0:
                return i, min(len(text), i + max(len(head), len(q)))
    return None


def _has_number(text: str) -> bool:
    """Есть ли в абзаце число, кроме номера пункта в начале («3.2. …»)."""
    return bool(re.search(r"\d", re.sub(r"^\s*\d+(?:\.\d+)*[.)]?\s", "", text)))


def parse_answer(answer: str, chunk: List[Block]) -> List[Finding]:
    """Строки ответа модели → находки. Строка без существующего номера фрагмента или без найденной цитаты отбрасывается."""
    found: List[Finding] = []
    for line in (answer or "").splitlines():
        m = LINE.match(line.strip())
        if not m:
            continue
        kind, a, b, quote, why = m.group(1).upper(), int(m.group(2)), m.group(3), m.group(4), m.group(5).strip()
        if not 1 <= a <= len(chunk) or len(why) < 8:
            continue
        block = chunk[a - 1]
        quote = " ".join(quote.split()[:14])                  # длинную цитату помечаем по началу — иначе пометка на весь абзац
        place = _locate(quote, block)
        if place is None:                             # модель перепутала номер фрагмента — ищем цитату в соседних
            for other in chunk:
                place = _locate(quote, other)
                if place:
                    block = other
                    break
        if place is None:
            continue
        other_note = ""
        if kind == "ПРОТИВОРЕЧИЕ":
            # противоречие — это два разных места с числами; расплывчатое «одно другому мешает» модель выдумывает часто
            second_block = chunk[int(b) - 1] if b and 1 <= int(b) <= len(chunk) else None
            if second_block is None or second_block is block or not _has_number(block.text) or not _has_number(second_block.text):
                continue
        if kind == "ПРОТИВОРЕЧИЕ" and b and 1 <= int(b) <= len(chunk) and chunk[int(b) - 1] is not block:
            second = " ".join(chunk[int(b) - 1].text.split())
            other_note = f" Сравните с местом: «{second[:140]}{'…' if len(second) > 140 else ''}»"
        why = why[:1].upper() + why[1:] + ("" if why.endswith((".", "!", "?")) else ".")
        contradiction = kind == "ПРОТИВОРЕЧИЕ"
        f = Finding("ai-contradiction" if contradiction else "ai-risk", "warning" if contradiction else "info",
                    "Смысл" if contradiction else "Риски",
                    "Возможное противоречие" if contradiction else "Рискованное условие",
                    why + other_note, block.index, place[0], place[1], block.text[place[0]:place[1]], None)
        f.ai = True
        if not any(x.block == f.block and x.start == f.start and x.rule == f.rule for x in found):
            found.append(f)
        if len(found) >= MAX_PER_CHUNK:
            break
    return found


def semantic_check(ctx: Context, llm) -> dict:
    """Добавляет в ctx находки модели. Возвращает сведения о проходе: сколько кусков прочитано и всего."""
    if llm is None or not llm.status().get("available"):
        return {"available": False, "chunks": 0, "total": 0, "found": 0}
    chunks = _chunks(ctx.blocks)
    added = 0
    done = 0
    for chunk in chunks[:MAX_CHUNKS]:
        text = "\n".join(f"[{n}] {' '.join(b.text.split())}" for n, b in enumerate(chunk, 1))
        answer = llm.generate(SYSTEM, f"Текст документа по фрагментам:\n{text}\n\n{TASK}", max_tokens=420)
        done += 1
        if not answer:
            continue
        for f in parse_answer(answer, chunk):
            ctx.findings.append(f)
            added += 1
    return {"available": True, "chunks": done, "total": len(chunks), "found": added,
            "model": llm.status().get("model")}
