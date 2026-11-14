"""
Перекрёстная сверка документа с остальными документами базы (этап 7).

Что сверяется:
- реквизиты организации: тот же контрагент в другом документе записан с другим ИНН, КПП или расчётным счётом;
- один ИНН — разные названия организаций;
- представитель: организацию в другом документе подписывает другой человек (сменился директор — приказ новее договора);
- ссылки на документы: «по договору № 124-А от 21.07.2025» — такой договор ищется в базе, сверяются дата,
  стороны и сумма (счёт или акт не должен быть больше цены договора).

Текст других документов берётся из поискового индекса (index.docs), то есть из их последних сохранённых версий.
Находка ставится в проверяемом документе и несёт поле source — с каким документом и местом она сверена.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional

from app.checks.blocks import Block
from app.checks.rules import Context, Finding, SP, _iter_dates

ORG = re.compile(r"\b(ООО|АО|ПАО|ЗАО|ОАО|НКО|ФГУП|МУП|ГУП)" + SP + r"*[«\"]([^»\"]{2,80})[»\"]")
INN = re.compile(r"ИНН(?:" + SP + r"*/" + SP + r"*КПП)?" + SP + r"*:?" + SP + r"*(\d{10}|\d{12})\b")
KPP = re.compile(r"КПП" + SP + r"*:?" + SP + r"*(\d{9})\b")
INN_KPP = re.compile(r"ИНН" + SP + r"*/" + SP + r"*КПП" + SP + r"*:?" + SP + r"*\d{10}" + SP + r"*/" + SP + r"*(\d{9})\b")
ACCOUNT = re.compile(r"(?:р/с|р\.?" + SP + r"?с\.|расч[её]тный" + SP + r"+сч[её]т)" + SP + r"*(?:№" + SP + r"*)?:?" + SP + r"*(\d{20})\b", re.IGNORECASE)
HEAD = re.compile(r"в" + SP + r"+лице" + SP + r"+((?:[а-яё]+" + SP + r"+){1,4}?)([А-ЯЁ][а-яё]+(?:" + SP + r"+[А-ЯЁ][а-яё]+){1,2}|[А-ЯЁ][а-яё]+" + SP + r"+[А-ЯЁ]\." + SP + r"*[А-ЯЁ]\.)")
KINDS = [("supplement", r"доп(?:\.|олнительн[а-яё]*)" + SP + r"*соглашени[а-яё]*"), ("contract", r"договор[а-яё]*|контракт[а-яё]*"),
         ("invoice", r"сч[её]т[а-яё]*(?:-фактур[а-яё]*)?"), ("act", r"акт[а-яё]*"), ("order", r"приказ[а-яё]*")]
KIND_NAME = {"contract": "Договор", "invoice": "Счёт", "act": "Акт", "order": "Приказ", "supplement": "Доп. соглашение"}
REF = re.compile(r"\b(" + "|".join(rx for _, rx in KINDS) + r")((?:" + SP + r"+[а-яё-]+){0,3}?)" + SP + r"*№" + SP
                 + r"*([A-Za-zА-Яа-яЁё0-9][\w\-/.]*[\wА-Яа-я]|\d)", re.IGNORECASE)
REQUISITE_REACH = 8       # столько абзацев после названия организации её реквизиты ещё считаются её реквизитами


def _core(name: str) -> str:
    return re.sub(r"[\s\-–—.,]+", " ", name.lower().replace("ё", "е")).strip()


def _kind(text: str) -> Optional[str]:
    low = text.lower()
    for kind, rx in KINDS:
        if re.match(r"\s*(?:" + rx + r")\b", low):
            return kind
    return None


def _number(n: str) -> str:
    return re.sub(r"[\s.]+$", "", n).lower().replace("ё", "е")


def _surname(person: str) -> str:
    return person.split()[0].lower().replace("ё", "е")[:6]      # первые буквы — падеж не мешает сравнению


def profile(blocks: List[str], title: str = "") -> dict:
    """Что документ говорит о себе и своих сторонах: вид, номер, дата, сумма, организации с реквизитами, ссылки."""
    from app.search.fields import extract_fields
    fields = extract_fields("".join(f"<p>{_escape(b)}</p>" for b in blocks))
    head_text = next((b for b in blocks if b.strip()), "")
    kind = _kind(title) or _kind(head_text)
    orgs: Dict[str, dict] = {}
    current, current_at = None, -99
    for i, text in enumerate(blocks):
        found = list(ORG.finditer(text))
        for k, m in enumerate(found):
            core = _core(m.group(2))
            org = orgs.setdefault(core, {"name": f"{m.group(1)} «{m.group(2).strip()}»", "core": core, "block": i, "span": m.span()})
            current, current_at = org, i
            end = found[k + 1].start() if k + 1 < len(found) else len(text)
            _requisites(org, text, m.end(), end, i)
        if not found and current is not None and i - current_at <= REQUISITE_REACH:
            _requisites(current, text, 0, len(text), i)
    refs = []
    for i, text in enumerate(blocks):
        for m in REF.finditer(text):
            kind_ref = _kind(m.group(1))
            number = _number(m.group(3))
            if i <= 1 and number == _number(fields.get("number") or ""):
                continue                                            # это собственный заголовок документа
            tail = text[m.end():m.end() + 40]
            d = next((x[0] for x in _iter_dates(tail) if x[0] and re.match(r"\s*от\s", tail, re.IGNORECASE)), None)
            refs.append({"kind": kind_ref, "number": number, "date": d, "block": i, "span": (m.start(), m.end())})
    return {"kind": kind, "number": _number(fields.get("number") or "") or None, "date": _date(fields.get("date")),
            "amount": fields.get("amount"), "orgs": orgs, "refs": refs}


def _requisites(org: dict, text: str, start: int, end: int, block: int) -> None:
    part = text[start:end]
    for key, rx in (("inn", INN), ("kpp", KPP), ("kpp", INN_KPP), ("account", ACCOUNT)):
        m = rx.search(part)
        if m and key not in org:
            org[key] = {"value": m.group(1), "block": block, "span": (start + m.start(1), start + m.end(1))}
    m = HEAD.search(part)
    if m and "head" not in org:
        org["head"] = {"value": m.group(2).strip(), "block": block, "span": (start + m.start(2), start + m.end(2))}


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _date(iso) -> Optional[date]:
    try:
        return date.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def _ru(d: Optional[date]) -> str:
    return d.strftime("%d.%m.%Y") if d else "без даты"


def _profile_of(index, doc_id: int) -> dict:
    doc = index.docs[doc_id]
    if "profile" not in doc:                          # запись документа в индексе пересоздаётся при сохранении — кэш не устаревает
        doc["profile"] = profile(doc["blocks"], doc.get("title") or "")
    return doc["profile"]


def _label(index, doc_id: int, p: dict) -> str:
    title = " ".join((index.docs[doc_id].get("title") or "Документ").split())
    return title[:70] + ("…" if len(title) > 70 else "")


def cross_check(ctx: Context, doc_id: int, index) -> dict:
    """Сверяет проверяемый документ (ctx) с остальными документами индекса. Возвращает сводку прохода."""
    mine = profile([b.text for b in ctx.blocks], (index.docs.get(doc_id) or {}).get("title") or "")
    my_texts = tuple(b.text for b in ctx.blocks)
    others = {}
    for d, doc in index.docs.items():
        if d == doc_id or tuple(doc["blocks"]) == my_texts:       # копии этого же документа сверять не с чем
            continue
        others[d] = _profile_of(index, d)
    added = 0

    def add(rule, severity, title, why, place, other_id, other_place=None, text=None):
        nonlocal added
        block = ctx.blocks[place["block"]]
        s, e = place["span"]
        f = Finding(rule, severity, "Сверка с базой", title, why, block.index, s, e, block.text[s:e], None)
        f.source = {"text": text or f"Сверено с документом «{_label(index, other_id, others[other_id])}»",
                    "doc": _label(index, other_id, others[other_id]), "docId": other_id,
                    "block": other_place["block"] if other_place else None,
                    "start": other_place["span"][0] if other_place else None, "end": other_place["span"][1] if other_place else None}
        ctx.findings.append(f)
        added += 1

    # --- реквизиты и представитель одной и той же организации
    for core, org in mine["orgs"].items():
        for key, what, severity in (("inn", "ИНН", "critical"), ("kpp", "КПП", "warning"), ("account", "Расчётный счёт", "info")):
            if key not in org:
                continue
            same, differ = [], []
            for d, p in others.items():
                o = p["orgs"].get(core)
                if o and key in o:
                    (same if o[key]["value"] == org[key]["value"] else differ).append((d, o))
            if differ and len(differ) >= len(same):           # большинство документов базы говорит другое
                d, o = differ[0]
                more = f" Так же — ещё в {len(differ) - 1} док." if len(differ) > 1 else ""
                add("cross-" + key, severity, f"{what} отличается от других документов",
                    f"У {org['name']} здесь {what} {org[key]['value']}, а в документе «{_label(index, d, others[d])}» — {o[key]['value']}.{more} "
                    "Проверьте, где ошибка: сверьте с выпиской ЕГРЮЛ или карточкой предприятия.", org[key], d, o[key])
        if "head" in org:
            for d, p in sorted(others.items(), key=lambda kv: kv[1]["date"] or date.min, reverse=True):
                o = p["orgs"].get(core)
                if not o or "head" not in o or _surname(o["head"]["value"]) == _surname(org["head"]["value"]):
                    continue
                newer = bool(p["date"] and mine["date"] and p["date"] > mine["date"])
                add("cross-head", "warning" if newer else "info", "Другой представитель организации",
                    f"Здесь {org['name']} представляет {org['head']['value']}, а в документе «{_label(index, d, p)}» от {_ru(p['date'])} — "
                    f"{o['head']['value']}." + (" Тот документ новее: возможно, руководитель сменился." if newer else
                                                " Проверьте, кто вправе подписывать на дату этого документа."), org["head"], d, o["head"])
                break
        if "inn" in org:                                       # тот же ИНН у организации с другим названием
            for d, p in others.items():
                o = next((x for c, x in p["orgs"].items() if c != core and x.get("inn", {}).get("value") == org["inn"]["value"]), None)
                if o:
                    add("cross-inn-name", "warning", "Этот ИНН записан за другой организацией",
                        f"ИНН {org['inn']['value']} здесь указан у {org['name']}, а в документе «{_label(index, d, p)}» — у {o['name']}. "
                        "ИНН у каждой организации свой: в одном из документов ошибка.", org["inn"], d, o["inn"])
                    break

    # --- ссылки на другие документы: есть ли такой в базе и сходятся ли дата, стороны, сумма
    seen = set()
    for ref in mine["refs"]:
        key = (ref["kind"], ref["number"])
        if key in seen or ref["kind"] not in ("contract", "supplement", "invoice", "act"):
            continue
        seen.add(key)
        match = [(d, p) for d, p in others.items() if p["number"] == ref["number"] and (p["kind"] in (ref["kind"], None))]
        if not match:
            continue                                           # документа в базе нет — сверять не с чем, шум не создаём
        d, p = match[0]
        name = KIND_NAME.get(ref["kind"], "Документ")
        if ref["date"] and p["date"] and ref["date"] != p["date"]:
            add("cross-ref-date", "warning", "Дата в ссылке не совпадает с документом",
                f"Здесь указано «от {_ru(ref['date'])}», а {name.lower()} № {ref['number']} в базе датирован {_ru(p['date'])}.", ref, d)
        if mine["orgs"] and p["orgs"] and not set(mine["orgs"]) & set(p["orgs"]):
            add("cross-ref-party", "warning", "Стороны не совпадают с документом по ссылке",
                f"{name} № {ref['number']} в базе заключён между: {', '.join(o['name'] for o in p['orgs'].values())}. "
                "В этом документе таких организаций нет.", ref, d)
        if ref["kind"] in ("contract", "supplement") and mine["kind"] in ("invoice", "act") and mine["amount"] and p["amount"] \
                and mine["amount"] > p["amount"] * 1.0001:
            add("cross-ref-amount", "warning", "Сумма больше цены договора",
                f"Сумма этого документа — {_money(mine['amount'])}, а цена по договору № {ref['number']} — {_money(p['amount'])}.", ref, d)
    return {"documents": len(others), "found": added}


def _money(v: float) -> str:
    return f"{int(round(v)):,}".replace(",", " ") + " ₽"
