"""
Ассистент по базе документов.

Принцип: цифры и список документов всегда считаются точно — по карточкам (тип, дата, контрагент, сумма, срок)
и полнотекстовому индексу. Языковая модель, если подключена, только формулирует короткий вывод
по уже отобранным фактам, поэтому не может «придумать» сумму или документ.

Вопрос разбирается на части: тип документа, период, контрагент, намерение (сроки, замечания, группировка)
и остаток слов — он уходит в поиск по тексту. Уточнения («за декабрь», «по контрагентам») дополняют
предыдущий вопрос: клиент присылает обратно context из прошлого ответа.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import List, Optional

from app.search.index import STOP, _expand
from app.search.stemmer_ru import tokens

MAX_ROWS = 50

# (код типа, шаблон в вопросе, формы слова: 1 / 2–4 / 5+)
TYPES = [
    ("SUPPLEMENTARY_AGREEMENT", r"\bдоп(?:\.|олнительн\w*)?\s*соглашени\w*", ("доп. соглашение", "доп. соглашения", "доп. соглашений")),
    ("CLAIM", r"\bпретензи\w*", ("претензия", "претензии", "претензий")),
    ("BUDGET", r"\bбюджет\w*|\bсмет\w*", ("бюджет", "бюджета", "бюджетов")),
    ("ORDER", r"\bприказ\w*", ("приказ", "приказа", "приказов")),
    ("MEMO", r"\bслужебн\w*(?:\s+записк\w*)?|\bзаписк\w*", ("служебная записка", "служебные записки", "служебных записок")),
    ("REGULATION", r"\bрегламент\w*|\bположени[еяйю]\w*|\bинструкци\w*", ("регламент", "регламента", "регламентов")),
    ("TECH_SPEC", r"\bтехническ\w*\s+задани\w*|\bтз\b", ("ТЗ", "ТЗ", "ТЗ")),
    ("CONTRACT", r"\bдоговор\w*|\bконтракт\w*", ("договор", "договора", "договоров")),
    ("INVOICE", r"\bсчет\w*", ("счёт", "счёта", "счетов")),
    ("ACT", r"\bакт(?:ы|а|ов|ам|ами|ах|у|ом|е)?\b", ("акт", "акта", "актов")),
    ("WAYBILL", r"\bнакладн\w*", ("накладная", "накладные", "накладных")),
]
TYPE_FORMS = {code: forms for code, _, forms in TYPES}
DOC_FORMS = ("документ", "документа", "документов")
TYPE_NOM = {"SUPPLEMENTARY_AGREEMENT": "доп. соглашения", "CLAIM": "претензии", "BUDGET": "бюджеты", "ORDER": "приказы",
            "MEMO": "служебные записки", "REGULATION": "регламенты", "TECH_SPEC": "ТЗ", "CONTRACT": "договоры",
            "INVOICE": "счета", "ACT": "акты", "WAYBILL": "накладные"}

MONTHS = [r"январ\w*", r"феврал\w*", r"март\w*", r"апрел\w*", r"ма[йяе]", r"июн\w*", r"июл\w*", r"август\w*",
          r"сентябр\w*", r"октябр\w*", r"ноябр\w*", r"декабр\w*"]
MONTH_NAMES = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
MONTH_IN = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре", "ноябре", "декабре"]

YEAR = re.compile(r"\b(20\d\d)\b(?:\s*(?:году|года|год|г\.?))?")
EXPIRING = re.compile(r"\bистека\w*|\bистек\w*|\bзаканчива\w*|\bоканчива\w*|\bсрок\w*\s+действи\w*|\bпролонг\w*|\bпродлева\w*|\bпродлит\w*")
HORIZON = re.compile(r"(?:\bв\s+)?(?:\bближайш\w*\s+)?(\d{1,3})\s+(?:дн\w*|день|суток)")
PROBLEMS = re.compile(r"\bошибк\w*|\bошибочн\w*|\bзамечани\w*|\bкритичн\w*|\bпроблем\w*|\bнесостыков\w*")
SUMS = re.compile(r"\bсумм\w*|\bитог\w*|\bвсего\b|\bобщ(?:ая|ую|ей|ий)\b|\bстоимост\w*|\bпотра\w*|\bденег\b|\bрубл\w*")
# «сколько» — про деньги, только если больше спрашивать не о чем («сколько договоров», но не «сколько этапов в ТЗ»)
HOW_MANY = re.compile(r"\bсколько\b")
# вопросительные слова в поиск по тексту не идут
QUESTION_WORDS = set("сколько какой какая какие какое каков какова каковы что чего чем где когда кто кем кому почему зачем как "
                     "ли есть этом этого этот эта данном документе документа документ скажи расскажи указан указана указано".split())
GROUP = re.compile(r"\bпо\s+(?:контрагент\w*|поставщик\w*|организаци\w*|компани\w*)")
RESET = re.compile(r"\bвс[ея]\b|\bвсех\b|\bвесь\b")
BRIEF = re.compile(r"^\s*кратко\s*[:—-]?\s*(.+)$", re.IGNORECASE | re.DOTALL)
# слова, которые не несут смысла для поиска по тексту
FUNCTIONAL = re.compile(r"документ\w*|найди|найти|покажи\w*|показать|выведи|дай|какие|какой|какая|каких|какую|есть|список|перечень|"
                        r"мне|нужн\w+|только|ооо|ао|пао|зао|ип|год\w*|месяц\w*|период\w*|ближайш\w*|которы\w+|у\s*нас|нас")
STOP_WORDS = set("и в во на по с со о об к ко за для от до не ни что это как так же бы ли или а но из у при без над под".split())


def _plural(n: int, forms) -> str:
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def money(v: float) -> str:
    return f"{int(round(v)):,}".replace(",", " ") + " ₽"


def _ru_date(iso: Optional[str]) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else ""


def _to_date(iso: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(iso[:10]) if iso else None
    except ValueError:
        return None


def _core(party: str) -> str:
    """Название без формы собственности: ООО «Вектор Снаб» → Вектор Снаб."""
    m = re.search(r"«([^»]+)»", party)
    return m.group(1) if m else re.sub(r"^(?:ИП|ООО|АО|ПАО|ЗАО)\s+", "", party)


def _stems(text: str) -> List[str]:
    return [s for s, _, _ in tokens(text)]


# ---------------------------------------------------------------------- разбор вопроса
def parse(question: str, docs: List[dict]) -> dict:
    q = question.lower().replace("ё", "е")
    used: List[tuple] = []

    def take(pattern) -> Optional[re.Match]:
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        found = None
        for m in rx.finditer(q):
            used.append(m.span())
            found = found or m
        return found

    types = [code for code, rx, _ in TYPES if take(rx)]
    # «доп. соглашение к договору» — не договор
    if "SUPPLEMENTARY_AGREEMENT" in types and "CONTRACT" in types:
        types.remove("CONTRACT")

    month = next((i + 1 for i, rx in enumerate(MONTHS) if take(r"\b" + rx + r"\b")), None)
    ym = take(YEAR)
    year = int(ym.group(1)) if ym else None

    hm = take(HORIZON)
    expiring = bool(take(EXPIRING)) or bool(hm)
    problems = bool(take(PROBLEMS))
    sums = bool(take(SUMS))
    how_many = bool(take(HOW_MANY))
    group = bool(take(GROUP))
    reset = bool(take(RESET))

    # контрагент: совпадение слов названия с известными из карточек
    q_tokens = [(s, a, b) for s, a, b in tokens(q)]
    q_stems = {s for s, _, _ in q_tokens}
    best, best_score, best_stems = None, 0, set()
    for name in dict.fromkeys(p for d in docs for p in (d.get("counterparties") or [])):
        core = {s for s in _stems(_core(name)) if len(s) >= 3 and s not in STOP_WORDS}
        hit = core & q_stems
        if hit and (hit == core or any(len(s) >= 4 for s in hit)) and len(hit) > best_score:
            best, best_score, best_stems = name, len(hit), hit

    words = []
    for s, a, b in q_tokens:
        word = q[a:b]
        if any(a < e and b > st for st, e in used) or s in best_stems or word in STOP_WORDS or FUNCTIONAL.fullmatch(word) \
                or word in QUESTION_WORDS:
            continue
        words.append(question[a:b])
    sums = sums or (how_many and not words)

    return {"types": types, "month": month, "year": year, "party": best, "expiring": expiring,
            "horizon": int(hm.group(1)) if hm else None, "problems": problems, "sums": sums, "group": group,
            "reset": reset, "text": " ".join(words)}


def _merge(ctx: dict, p: dict) -> dict:
    """Уточнение дополняет прошлый вопрос: новое значение заменяет старое, пустое — оставляет."""
    out = dict(ctx)
    for k in ("month", "year", "party", "horizon"):
        if p.get(k) is not None:
            out[k] = p[k]
    for k in ("expiring", "problems", "sums", "group"):
        out[k] = bool(ctx.get(k)) or bool(p.get(k))
    out["reset"] = False
    return out


# ---------------------------------------------------------------------- вспомогательное
def _amount_place(blocks: List[str], amount: float) -> Optional[dict]:
    """Место в тексте, где записана сумма: по нему редактор откроет документ и покажет цитату."""
    digits = str(int(round(amount)))
    rx = re.compile(r"(?<!\d)" + r"[\s  ]?".join(digits) + r"(?!\d)")
    for i, text in enumerate(blocks):
        m = rx.search(text)
        if m:
            a, b = max(0, m.start() - 70), min(len(text), m.end() + 50)
            quote = ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")
            return {"block": i, "start": m.start(), "end": m.end(), "quote": quote}
    return None


def _row(n: int, d: dict, today: date) -> dict:
    vu = _to_date(d.get("validUntil"))
    parties = d.get("counterparties") or []
    title = " ".join((d.get("title") or "Документ").split())
    title = title[:117] + "…" if len(title) > 120 else title
    return {"n": n, "id": d["id"], "title": title, "typeName": d.get("typeName") or "",
            "number": d.get("number"), "date": d.get("date"), "party": parties[0] if parties else None,
            "amount": d.get("amount"), "validUntil": d.get("validUntil"),
            "daysLeft": (vu - today).days if vu else None,
            "critical": d.get("critical") or 0, "warning": d.get("warning") or 0, "checked": bool(d.get("checked")),
            "block": None, "start": None, "end": None, "quote": None, "snippet": False}


def _titles(rows: List[dict], limit: int = 3) -> str:
    names = [f"«{r['title']}» [{r['n']}]" for r in rows[:limit]]
    return ", ".join(names) + (f" и ещё {len(rows) - limit}" if len(rows) > limit else "")


def _period_label(ctx: dict, in_form: bool = False) -> str:
    m, y = ctx.get("month"), ctx.get("year")
    if m:
        return (MONTH_IN if in_form else MONTH_NAMES)[m - 1] + (f" {y}" if y else "")
    return f"{y} год" + ("у" if in_form else "") if y else ""


def _clean_refs(text: str, count: int) -> str:
    """Убирает из ответа модели ссылки на несуществующие источники."""
    return re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= count else "", text).strip()


def _llm_note(llm) -> dict:
    st = llm.status() if llm else {"available": False, "model": None}
    return {"available": bool(st.get("available")), "model": st.get("model")}


SYSTEM = ("Ты — помощник по корпоративным документам. Отвечай по-русски, кратко и только по приведённым данным. "
          "Ничего не придумывай: если в данных нет прямого ответа на вопрос, так и напиши — «в документе это не указано» — "
          "и не подменяй ответ похожими сведениями. Числа и названия бери из данных без изменений, сам ничего не складывай и не считай. "
          "После каждого утверждения ставь ссылку на источник в квадратных скобках, например [1].")


NOT_STATED = re.compile(r"не указан|нет прямого ответа|не имеет прямого ответа|не содерж", re.IGNORECASE)


def _tidy(text: str) -> str:
    """Приводит ответ модели в порядок: дежурное «в документе это не указано» после содержательного ответа убирается,
    а если весь ответ — «не указано», у него не остаётся ссылок на источники (ссылаться не на что)."""
    parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«])", text.strip()) if x.strip()]
    solid = [x for x in parts if not (NOT_STATED.search(x) and len(x.split()) <= 8)]
    if solid and len(solid) < len(parts):
        return " ".join(solid)
    if not solid:
        out = re.sub(r"\s*\[\d+\]", "", " ".join(parts)).strip()
        return out[:1].upper() + out[1:] + ("" if out.endswith((".", "!", "?")) else ".")
    return text.strip()


def _ask_llm(llm, question: str, facts: List[str], task: str, count: int) -> Optional[str]:
    if not llm or not llm.status().get("available"):
        return None
    prompt = f"Вопрос пользователя: {question}\n\nДанные из базы документов:\n" + "\n".join(facts) + f"\n\n{task}"
    out = llm.generate(SYSTEM, prompt, max_tokens=260)
    return _tidy(_clean_refs(out, count)) if out else None


# ---------------------------------------------------------------------- вопрос по тексту
def _terms(question: str) -> set:
    """Основы значимых слов вопроса вместе с синонимами — по ним выбираются места в тексте."""
    q = question.lower().replace("ё", "е")
    out = set()
    for s, a, b in tokens(q):
        if s in STOP or q[a:b] in QUESTION_WORDS or q[a:b] in STOP_WORDS:
            continue
        out.add(s)
        out.update(_expand(s))
    return out


SIM_FLOOR = 0.4      # ниже этой близости смысловой отпечаток абзаца в расчёт не берётся


def _sims(index, doc_id: int, question: str):
    """Близость вопроса к абзацам документа по смыслу; None, если смысловой индекс не подключён или ещё не готов."""
    try:
        return index.block_sims(doc_id, index.query_vec(question))
    except AttributeError:
        return None


def _fragments(blocks: List[str], terms: set, limit: int = 8, width: int = 600, sims=None) -> List[dict]:
    """Самые подходящие к вопросу абзацы: {block, start, end, text, score}, в порядке текста.
    Оценка — число разных слов вопроса в абзаце плюс близость по смыслу (если есть отпечатки)."""
    scored = []
    for i, text in enumerate(blocks):
        hits = [(s, a, b) for s, a, b in tokens(text) if s in terms]
        sim = float(sims[i]) if sims is not None and i < len(sims) else 0.0
        bonus = 5 * (sim - SIM_FLOOR + 0.1) if sim >= SIM_FLOOR else 0.0
        if hits or bonus:
            scored.append((len({s for s, _, _ in hits}) + bonus, len(hits), i, hits))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    out = []
    for score, _, i, hits in scored[:limit]:
        text = blocks[i]
        first = hits[0][1] if hits else 0
        a = 0 if len(text) <= width else max(0, min(first - width // 4, len(text) - width))
        cut = text[a:a + width].strip()
        out.append({"block": i, "start": hits[0][1] if hits else None, "end": hits[0][2] if hits else None, "score": round(score, 2),
                    "text": ("…" if a else "") + cut + ("…" if a + width < len(text) else "")})
    out.sort(key=lambda f: f["block"])
    return out


HEADING = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]|раздел|глава|статья|приложение)\s", re.IGNORECASE)
WHOLE_DOC = 5000          # документ короче этого уходит в модель целиком


def ask_document(question: str, doc_id: int, index, llm=None) -> dict:
    """Вопрос по одному открытому документу. Источники — абзацы документа; редактор прокручивает к ним."""
    blocks = (index.docs.get(doc_id) or {}).get("blocks") or []
    base = {"kind": "doc", "headline": None, "filters": [], "table": None, "groups": None, "alerts": [], "followups": [],
            "context": None, "llm": _llm_note(llm)}
    if not any(b.strip() for b in blocks):
        return {**base, "found": False, "steps": ["Текст документа не найден в индексе"], "sources": [], "generated": False,
                "summary": "Не вижу текста этого документа. Сохраните документ и задайте вопрос ещё раз."}
    terms = _terms(question)
    matched = _fragments(blocks, terms, 8, 600, _sims(index, doc_id, question))
    filled = [i for i, b in enumerate(blocks) if b.strip()]
    if sum(len(b) for b in blocks) <= WHOLE_DOC:
        by_block = {f["block"]: f for f in matched}
        frags = [{**(by_block.get(i) or {"block": i, "start": None, "end": None, "score": 0}), "text": blocks[i].strip()} for i in filled]
        note = "Прочитал документ целиком"
    else:
        frags = matched
        note = f"Выбрал {len(frags)} {_plural(len(frags), ('подходящий абзац', 'подходящих абзаца', 'подходящих абзацев'))} из {len(filled)}"
    for n, f in enumerate(frags, 1):
        f["n"] = n
    steps = [note]
    facts = [f"[{f['n']}] {f['text']}" for f in frags]
    heads = [b.strip() for b in blocks if len(b.strip()) < 90 and HEADING.match(b)]
    if heads and len(frags) < len(filled):
        facts.append("Заголовки разделов документа по порядку: " + "; ".join(heads[:40]))

    generated = None
    if facts:
        generated = _ask_llm(llm, question, facts,
                             "Ответь на вопрос по этому документу в 1–3 предложениях. После каждого утверждения ставь номер фрагмента, "
                             "например [2]. Если прямого ответа во фрагментах нет — так и напиши.", len(frags))
    best = sorted([f for f in frags if f["score"]], key=lambda f: -f["score"])[:3]
    if generated:
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", generated)}
        used = [f for f in frags if f["n"] in cited] or sorted(best[:2], key=lambda f: f["block"])
        summary = generated
        steps.append("Сформулировал ответ языковой моделью")
    elif best:
        used = sorted(best, key=lambda f: f["block"])
        summary = "По этому вопросу в документе нашлись такие места: " + " ".join(f"[{f['n']}]" for f in used) \
                  + ". Готовый ответ появится после подключения языковой модели."
        steps.append("Нашёл подходящие места в тексте")
    else:
        return {**base, "found": False, "steps": steps + ["Подходящих мест нет"], "sources": [], "generated": False,
                "summary": "В этом документе не нашёл ответа на вопрос. Попробуйте задать его другими словами."}
    sources = [{"n": f["n"], "block": f["block"], "start": f["start"], "end": f["end"],
                "quote": f["text"][:160] + ("…" if len(f["text"]) > 160 else "")} for f in used[:6]]
    return {**base, "found": True, "steps": steps, "sources": sources, "summary": summary, "generated": bool(generated)}


# ---------------------------------------------------------------------- ответ
def answer(question: str, context: Optional[dict], docs: List[dict], index, llm=None, today: Optional[date] = None,
           doc_id: Optional[int] = None) -> dict:
    today = today or date.today()
    question = (question or "").strip()
    if doc_id is not None:
        return ask_document(question, doc_id, index, llm)
    brief = BRIEF.match(question)
    if brief:
        return _brief(brief.group(1).strip(), docs, index, llm, today)

    p = parse(question, docs)
    modifiers = p["month"] or p["year"] or p["party"] or p["expiring"] or p["problems"] or p["group"] or p["sums"]
    if context and not p["types"] and not p["text"] and not p["reset"] and modifiers:
        ctx = _merge(context, p)
    else:
        ctx = p
    structured = bool(ctx["types"] or ctx.get("party") or ctx.get("month") or ctx.get("year") or ctx.get("expiring")
                      or ctx.get("problems") or ctx.get("reset"))
    if not structured and not ctx.get("text"):
        return _not_found(question, ["Не понял, какие документы нужны"], llm,
                          "Уточните, какие документы нужны: тип (договоры, приказы, бюджеты), контрагент, период или слова из текста.")

    steps, chips, alerts = [], [], []
    rows_src = list(docs)

    if ctx["types"]:
        rows_src = [d for d in rows_src if d.get("type") in ctx["types"]]
        chips.append("Тип: " + ", ".join(TYPE_NOM[t] for t in ctx["types"]))
    if ctx.get("party"):
        core = _core(ctx["party"]).lower()
        rows_src = [d for d in rows_src if any(_core(x).lower() == core for x in (d.get("counterparties") or []))]
        chips.append("Контрагент: " + ctx["party"])
    typed = list(rows_src)

    if ctx.get("expiring"):
        with_term = [d for d in rows_src if _to_date(d.get("validUntil"))]
        no_term = len(rows_src) - len(with_term)
        if ctx.get("month"):
            y = ctx.get("year") or (today.year if ctx["month"] >= today.month else today.year + 1)
            rows_src = [d for d in with_term if (_to_date(d["validUntil"]).year, _to_date(d["validUntil"]).month) == (y, ctx["month"])]
            chips.append(f"Срок истекает: {MONTH_NAMES[ctx['month'] - 1]} {y}")
        elif ctx.get("year"):
            rows_src = [d for d in with_term if _to_date(d["validUntil"]).year == ctx["year"]]
            chips.append(f"Срок истекает: {ctx['year']} год")
        else:
            horizon = ctx.get("horizon") or 90
            limit = today + timedelta(days=horizon)
            overdue = [d for d in with_term if _to_date(d["validUntil"]) < today]
            rows_src = [d for d in with_term if today <= _to_date(d["validUntil"]) <= limit]
            chips.append(f"Срок истекает: ближайшие {horizon} {_plural(horizon, ('день', 'дня', 'дней'))}")
            if overdue:
                alerts.append(f"У {len(overdue)} {_plural(len(overdue), DOC_FORMS)} срок действия уже прошёл: "
                              + ", ".join(f"«{d.get('title')}» (до {_ru_date(d['validUntil'])})" for d in overdue[:3]) + ".")
        if no_term:
            alerts.append(f"В {no_term} {_plural(no_term, ('документе', 'документах', 'документах'))} срок действия в тексте не найден — проверьте их вручную.")
    elif ctx.get("month") or ctx.get("year"):
        def in_period(d):
            dt = _to_date(d.get("date")) or _to_date(d.get("created"))
            return bool(dt) and (not ctx.get("month") or dt.month == ctx["month"]) and (not ctx.get("year") or dt.year == ctx["year"])
        rows_src = [d for d in rows_src if in_period(d)]
        chips.append("Период: " + _period_label(ctx))

    if ctx.get("problems"):
        rows_src = [d for d in rows_src if (d.get("critical") or 0) + (d.get("warning") or 0) > 0]
        chips.append("С замечаниями проверки")

    described = "; ".join(chips) if chips else "поиск по тексту документов"
    steps.append("Понял запрос: " + described[0].lower() + described[1:])
    if structured:
        steps.append(f"Просмотрел карточки {len(docs)} {_plural(len(docs), DOC_FORMS)}, подошло {len(rows_src)}")

    snippets, extra = {}, {}
    text = ctx.get("text") or ""
    if text and rows_src:
        ids = [d["id"] for d in rows_src]
        hits = index.search(text, "words", ids, MAX_ROWS) or index.search(text, "sem", ids, MAX_ROWS)
        if hits:
            by_id = {d["id"]: d for d in rows_src}
            rows_src = [by_id[h["id"]] for h in hits if h["id"] in by_id]
            # сниппеты идут по порядку текста; для цитаты берём самый подходящий (rank 0)
            snippets = {h["id"]: min(h["snippets"], key=lambda sn: sn.get("rank", 0)) for h in hits if h.get("snippets")}
            extra = {h["id"]: [sn["text"] for sn in h["snippets"]] for h in hits if h.get("snippets")}
            steps.append(f"Искал в тексте: «{text}» — нашлось {len(rows_src)}")
            chips.append(f"В тексте: {text}")
        elif structured:
            steps.append(f"Искал в тексте: «{text}» — совпадений нет")
            alerts.append(f"Слов «{text}» в тексте этих документов нет — показаны все подходящие по остальным условиям.")
        else:
            rows_src = []

    if not rows_src:
        steps.append("Подходящих документов нет")
        msg = "В базе нет документов, которые подходят под запрос"
        if chips:
            msg += " (" + "; ".join(chips).lower() + ")"
        res = _not_found(question, steps, llm, msg + ". Я не буду придумывать ответ: попробуйте изменить условия.")
        res["alerts"] = alerts
        if typed and (ctx.get("expiring") or ctx.get("month") or ctx.get("year") or ctx.get("problems")):
            res["context"] = {**ctx, "month": None, "year": None, "expiring": False, "problems": False}
        return res

    # порядок: по сроку, по совпадению с текстом (как вернул поиск), по сумме или по дате
    if ctx.get("expiring"):
        rows_src.sort(key=lambda d: d["validUntil"])
    elif not snippets:
        if any(d.get("amount") for d in rows_src) and (ctx.get("sums") or "BUDGET" in ctx["types"]):
            rows_src.sort(key=lambda d: -(d.get("amount") or 0))
        else:
            rows_src.sort(key=lambda d: d.get("date") or d.get("created") or "", reverse=True)

    total_found = len(rows_src)
    if total_found > MAX_ROWS:
        alerts.append(f"Показаны первые {MAX_ROWS} из {total_found} документов — уточните запрос, чтобы сузить список.")
    rows = [_row(i + 1, d, today) for i, d in enumerate(rows_src[:MAX_ROWS])]
    for r in rows:
        blocks = (index.docs.get(r["id"]) or {}).get("blocks") or []
        sn = snippets.get(r["id"])
        if sn:
            quote = ("…" if sn.get("prefix") else "") + sn["text"] + ("…" if sn.get("suffix") else "")
            r.update(block=sn["block"], start=sn["start"], end=sn["end"], quote=quote, snippet=True)
        elif r["amount"]:
            place = _amount_place(blocks, r["amount"])
            if place:
                r.update(place)

    # вопрос по содержанию («что сказано про…») — суммы из карточек тут ни при чём, не показываем и не складываем
    by_text = bool(snippets) and not structured and not ctx.get("sums")
    with_amount = [] if by_text else [r for r in rows if r["amount"]]
    total = sum(r["amount"] for r in with_amount)
    forms = TYPE_FORMS[ctx["types"][0]] if len(ctx["types"]) == 1 else DOC_FORMS
    headline = f"По запросу: {{{total_found} {_plural(total_found, forms)}}}"
    if ctx.get("expiring"):
        headline += ", срок действия истекает"
    if with_amount:
        headline += f" на общую сумму {{{money(total)}}}" if len(with_amount) > 1 else f", сумма {{{money(total)}}}"
        steps.append("Взял суммы из текста документов и сложил их" if len(with_amount) > 1 else "Взял сумму из текста документа")

    columns = ["title", "date", "party"]
    if ctx.get("expiring"):
        columns.append("validUntil")
    if ctx.get("problems"):
        columns.append("check")
    if with_amount:
        columns.append("amount")

    table = {"columns": columns, "rows": rows, "total": total if len(with_amount) > 1 else None}
    groups = None
    if ctx.get("group"):
        agg = {}
        for r in rows:
            g = agg.setdefault(r["party"] or "Контрагент не указан", {"count": 0, "amount": 0.0, "refs": []})
            g["count"] += 1
            g["amount"] += r["amount"] or 0
            g["refs"].append(r["n"])
        groups = [{"group": k, **v, "share": round(v["amount"] / total * 100) if total else None}
                  for k, v in sorted(agg.items(), key=lambda kv: (-kv[1]["amount"], -kv[1]["count"]))]
        steps.append("Сгруппировал по контрагентам")

    # замечания к результату
    if with_amount and len(with_amount) < len(rows):
        missing = [r for r in rows if not r["amount"]]
        alerts.append(f"В {len(missing)} {_plural(len(missing), ('документе', 'документах', 'документах'))} сумма в тексте не найдена, в итог не вошли: {_titles(missing)}.")
    crit = [r for r in rows if r["critical"]]
    if crit and not ctx.get("problems"):
        alerts.append(f"Проверка нашла критичные замечания в {len(crit)} {_plural(len(crit), ('документе', 'документах', 'документах'))}: {_titles(crit)}.")

    # вывод: точные факты словами
    parts = []
    if groups and len(groups) > 1:
        g = groups[0]
        parts.append(f"Больше всего приходится на {g['group']}: {g['count']} {_plural(g['count'], DOC_FORMS)}"
                     + (f" на {money(g['amount'])} ({g['share']} % общей суммы)." if g["amount"] else "."))
    if ctx.get("expiring"):
        r = rows[0]
        left = r["daysLeft"]
        when = "сегодня" if left == 0 else (f"через {left} {_plural(left, ('день', 'дня', 'дней'))}" if left > 0
                                           else f"истёк {-left} {_plural(-left, ('день', 'дня', 'дней'))} назад")
        parts.append(f"Ближайший срок — «{r['title']}»: до {_ru_date(r['validUntil'])}, {when} [{r['n']}].")
    if snippets:
        r = rows[0]
        parts.append(f"Лучше всего подходит «{r['title']}» [{r['n']}]: «{r['quote']}»")
    if with_amount and not groups:
        top = max(with_amount, key=lambda r: r["amount"])
        s = f"{'Крупнейшая сумма' if len(with_amount) > 1 else 'Сумма'} — «{top['title']}»: {money(top['amount'])} [{top['n']}]"
        parts.append(s + (f", это {round(top['amount'] / total * 100)} % общей суммы." if len(with_amount) > 1 else "."))
    if ctx.get("problems"):
        worst = max(rows, key=lambda r: (r["critical"], r["warning"]))
        parts.append(f"Больше всего замечаний — «{worst['title']}»: критичных {worst['critical']}, прочих {worst['warning']} [{worst['n']}].")
    if not parts:
        r = rows[0]
        parts.append(f"Самый свежий — «{r['title']}»" + (f" от {_ru_date(r['date'])}" if r["date"] else "") + f" [{r['n']}].")
    summary = " ".join(parts)

    facts = []
    q_terms = _terms(text) if snippets else set()
    seen, copies = {}, []
    for r in rows[:12]:
        same = (r["title"], tuple((index.docs.get(r["id"]) or {}).get("blocks") or [r["id"]]))
        if same in seen:
            copies.append((seen[same], r["n"]))
            continue
        seen[same] = r["n"]
        bits = [f"[{r['n']}] {r['title']}"]
        if r["date"]:
            bits.append("дата " + _ru_date(r["date"]))
        if r["party"]:
            bits.append("контрагент " + r["party"])
        if r["amount"] and not by_text:
            bits.append("сумма " + money(r["amount"]).replace(" ", " "))
        elif with_amount:
            bits.append("сумма в документе не найдена")
        if r["validUntil"]:
            bits.append("действует до " + _ru_date(r["validUntil"]))
        quotes = extra.get(r["id"]) or ([r["quote"]] if r["quote"] else [])
        if snippets and r["n"] <= 3:      # из трёх лучших документов — абзацы целиком, а не обрывки
            doc_blocks = (index.docs.get(r["id"]) or {}).get("blocks") or []
            quotes = [f["text"] for f in _fragments(doc_blocks, q_terms, 3, 500, _sims(index, r["id"], text))] or quotes
        for qt in quotes[:3]:
            bits.append("цитата: «" + qt[:400] + "»")
        facts.append("; ".join(bits))
    if with_amount and len(with_amount) > 1:
        facts.append(f"Общая сумма по {len(with_amount)} документам с суммой: " + money(total).replace(" ", " "))
    if copies:
        first = copies[0][0]
        nums = [first] + [n for a, n in copies if a == first]
        alerts.append("Документы " + ", ".join(f"[{n}]" for n in nums) + " совпадают по названию и тексту — похоже, один файл загружен несколько раз.")
    generated = _ask_llm(llm, question, facts, "Ответь на вопрос в 2–4 предложениях со ссылками на источники.", len(rows))
    if generated:
        summary = generated
        steps.append("Сформулировал вывод языковой моделью")
    else:
        steps.append("Составил сводку")

    followups = []
    if not ctx.get("group") and len({r["party"] for r in rows}) > 1:
        followups.append("По контрагентам")
    if not ctx.get("problems") and any(r["critical"] or r["warning"] for r in rows) and len(rows) > 1:
        followups.append("Только с замечаниями")
    if not ctx.get("expiring") and any(r["validUntil"] for r in rows) and len(rows) > 1:
        followups.append("Истекающие в ближайшие 90 дней")
    if not ctx.get("month") and not ctx.get("expiring") and len(rows) > 1:
        common = Counter(r["date"][5:7] for r in rows if r["date"]).most_common(1)
        if common and common[0][1] < len(rows):
            followups.append("За " + MONTH_NAMES[int(common[0][0]) - 1])

    return {"found": True, "kind": "list", "steps": steps, "headline": headline, "filters": chips, "table": table,
            "groups": groups, "summary": summary, "generated": bool(generated), "alerts": alerts,
            "followups": followups, "context": ctx, "llm": _llm_note(llm)}


def _not_found(question: str, steps: List[str], llm, message: str) -> dict:
    return {"found": False, "kind": "empty", "steps": steps, "headline": None, "filters": [], "table": None, "groups": None,
            "summary": message, "generated": False, "alerts": [], "followups": [], "context": None, "llm": _llm_note(llm)}


def _brief(name: str, docs: List[dict], index, llm, today: date) -> dict:
    """«Кратко: <название>» — карточка документа и короткий пересказ."""
    low = name.lower()
    doc = next((d for d in docs if (d.get("title") or "").lower() == low), None) \
        or next((d for d in docs if low in (d.get("title") or "").lower()), None)
    if not doc:
        hits = index.search(name, "sem", [d["id"] for d in docs], 1) if docs else []
        doc = next((d for d in docs if hits and d["id"] == hits[0]["id"]), None)
    if not doc:
        return _not_found(name, ["Ищу документ по названию", "Документ не найден"], llm,
                          f"Документа «{name}» в базе нет. Проверьте название или найдите его через поиск.")
    r = _row(1, doc, today)
    blocks = (index.docs.get(doc["id"]) or {}).get("blocks") or []
    card = [["Тип", r["typeName"]], ["Номер", r["number"]], ["Дата", _ru_date(r["date"])],
            ["Стороны", ", ".join(doc.get("counterparties") or [])],
            ["Сумма", money(r["amount"]) if r["amount"] else None], ["Действует до", _ru_date(r["validUntil"])],
            ["Проверка", (f"критичных {r['critical']}, прочих замечаний {r['warning']}" if r["critical"] or r["warning"]
                          else "замечаний нет") if r["checked"] else "не проводилась"]]
    card = [c for c in card if c[1]]
    if r["amount"]:
        place = _amount_place(blocks, r["amount"])
        if place:
            r.update(place)

    body = [b.strip() for b in blocks[1:] if len(b.strip()) > 40]
    steps = ["Нашёл документ в базе", "Собрал карточку: реквизиты, сумма, срок, результаты проверки"]
    generated = None
    if blocks:
        text = "\n".join(blocks)[:6000]
        generated = _ask_llm(llm, f"Кратко о документе «{r['title']}»", ["[1] Текст документа:\n" + text],
                             "Перескажи документ в 3–4 предложениях: что это за документ, кто стороны, предмет, сумма и сроки.", 1)
    if generated:
        summary = generated
        steps.append("Пересказал текст языковой моделью")
    elif body:
        start = body[0][:320] + ("…" if len(body[0]) > 320 else "")
        summary = f"Начало текста [1]: «{start}»"
        steps.append("Показываю начало текста: пересказ появится после подключения языковой модели")
    else:
        summary = "В документе нет текста, который можно пересказать."
    alerts = []
    if r["critical"]:
        alerts.append(f"Проверка нашла критичные замечания: {r['critical']}. Откройте документ, чтобы посмотреть правки.")
    if r["daysLeft"] is not None and r["daysLeft"] < 0:
        alerts.append(f"Срок действия истёк {_ru_date(r['validUntil'])}.")
    elif r["daysLeft"] is not None and r["daysLeft"] <= 30:
        alerts.append(f"Срок действия истекает {_ru_date(r['validUntil'])} — через {r['daysLeft']} {_plural(r['daysLeft'], ('день', 'дня', 'дней'))}.")
    return {"found": True, "kind": "brief", "steps": steps, "headline": f"{{{r['title']}}}", "filters": [],
            "table": {"columns": [], "rows": [r], "total": None}, "groups": None, "card": card, "summary": summary,
            "generated": bool(generated), "alerts": alerts, "followups": [], "context": None, "llm": _llm_note(llm)}
