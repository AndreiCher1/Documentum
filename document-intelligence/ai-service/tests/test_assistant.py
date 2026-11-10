"""Тесты ассистента: разбор вопроса, отбор по карточкам, суммы, сроки, уточнения, поиск по тексту, модель."""

import os
import tempfile
from datetime import date

from app.assistant.engine import answer, parse
from app.search.fields import extract_fields
from app.search.index import SearchIndex

TODAY = date(2025, 11, 10)

SOURCES = [
    (1, "CONTRACT", "Договор", "<h1>ДОГОВОР АРЕНДЫ № 15/25</h1><p>г. Самара 1 марта 2025 г.</p>"
        "<p>ООО «Склад-Сервис» и ООО «Северный Терминал» заключили договор.</p>"
        "<p>1.1. Арендная плата составляет 210 000 (двести десять тысяч) рублей в месяц.</p>"
        "<p>2.1. Договор действует до 15 декабря 2025 г.</p>"),
    (2, "CONTRACT", "Договор", "<h1>ДОГОВОР ПОСТАВКИ № 124-А</h1><p>21.07.2025</p>"
        "<p>ООО «Вектор Снаб» и ООО «Северный Терминал» заключили договор поставки оборудования.</p>"
        "<p>Цена договора составляет 1 250 000 (один миллион двести пятьдесят тысяч) рублей.</p>"
        "<p>За просрочку поставки начисляется неустойка 0,1 % в день.</p>"
        "<p>Договор действует до 30 июня 2026 г.</p>"),
    (3, "BUDGET", "Бюджет", "<h1>Бюджет отдела маркетинга на декабрь</h1><p>27.11.2025</p>"
        "<p>Утвердить бюджет отдела маркетинга в сумме 3 150 000 рублей.</p>"),
    (4, "BUDGET", "Бюджет", "<h1>Бюджет отдела продаж на декабрь</h1><p>28.11.2025</p>"
        "<p>Утвердить бюджет отдела продаж в сумме 8 650 000 рублей.</p>"),
    (5, "BUDGET", "Бюджет", "<h1>Бюджет проекта «Склад-2»</h1><p>03.10.2025</p><p>Смета расходов уточняется.</p>"),
    (6, "ORDER", "Приказ", "<h1>ПРИКАЗ № 14-ОТ</h1><p>10.01.2025</p>"
        "<p>О назначении ответственного за охрану труда. Назначить Петрова П. П. ответственным за охрану труда.</p>"),
]


def setup():
    idx = SearchIndex(os.path.join(tempfile.mkdtemp(), "s.db"))
    docs = []
    for doc_id, code, name, html in SOURCES:
        f = extract_fields(html)
        idx.upsert(doc_id, f["title"], html)
        docs.append({"id": doc_id, "title": f["title"], "type": code, "typeName": name, "number": f["number"], "date": f["date"],
                     "created": "2025-11-01", "amount": f["amount"], "counterparties": f["counterparties"],
                     "validUntil": f["validUntil"], "critical": 2 if doc_id == 2 else 0, "warning": 0, "checked": True})
    return idx, docs


def ask(q, ctx=None, llm=None):
    idx, docs = setup()
    return answer(q, ctx, docs, idx, llm, TODAY)


def test_parse_question():
    _, docs = setup()
    p = parse("Договоры с Вектором, истекающие в декабре 2025 года", docs)
    assert p["types"] == ["CONTRACT"] and p["party"] == "ООО «Вектор Снаб»"
    assert p["month"] == 12 and p["year"] == 2025 and p["expiring"] and p["text"] == ""
    assert parse("приказы по охране труда", docs)["text"] == "охране труда"
    assert parse("доп. соглашения к договорам", docs)["types"] == ["SUPPLEMENTARY_AGREEMENT"]


def test_budgets_total_and_sources():
    r = ask("Бюджеты")
    assert r["found"] and len(r["table"]["rows"]) == 3
    assert r["table"]["total"] == 11_800_000
    top = r["table"]["rows"][0]
    assert top["amount"] == 8_650_000 and "8 650 000" in top["quote"] and top["block"] is not None
    assert "11 800 000" in r["headline"]
    assert any("сумма в тексте не найдена" in a for a in r["alerts"])       # «Склад-2» без суммы
    assert "[1]" in r["summary"]


def test_followup_keeps_context():
    first = ask("Бюджеты")
    second = ask("за ноябрь", first["context"])
    assert [x["id"] for x in second["table"]["rows"]] == [4, 3]
    assert second["table"]["total"] == 11_800_000
    fresh = ask("Все приказы", first["context"])
    assert [x["id"] for x in fresh["table"]["rows"]] == [6]


def test_expiring_contracts():
    r = ask("Договоры, истекающие в декабре")
    assert [x["id"] for x in r["table"]["rows"]] == [1]
    assert r["table"]["rows"][0]["daysLeft"] == 35 and "validUntil" in r["table"]["columns"]
    soon = ask("Какие договоры истекают в ближайшие 60 дней")
    assert [x["id"] for x in soon["table"]["rows"]] == [1]


def test_counterparty_and_grouping():
    r = ask("Все документы по ООО «Вектор Снаб»")
    assert [x["id"] for x in r["table"]["rows"]] == [2]
    assert any("критичные" in a for a in r["alerts"])
    g = ask("Договоры по контрагентам")
    assert g["groups"] and sum(x["count"] for x in g["groups"]) == 2


def test_text_search_and_fallback():
    r = ask("приказы по охране труда")
    assert [x["id"] for x in r["table"]["rows"]] == [6] and r["table"]["rows"][0]["snippet"]
    free = ask("неустойка за просрочку")
    assert free["table"]["rows"][0]["id"] == 2 and "неустойка" in free["table"]["rows"][0]["quote"]
    miss = ask("бюджеты про космодром")
    assert len(miss["table"]["rows"]) == 3 and any("космодром" in a for a in miss["alerts"])


def test_not_found_is_honest():
    r = ask("космодром байконур")
    assert not r["found"] and "не буду придумывать" in r["summary"]
    assert not ask("привет")["found"]
    assert not ask("Приказы за 2019 год")["found"]


def test_brief():
    r = ask("Кратко: ДОГОВОР ПОСТАВКИ № 124-А")
    assert r["kind"] == "brief" and r["table"]["rows"][0]["id"] == 2
    assert ["Сумма", "1 250 000 ₽"] in r["card"]
    assert not ask("Кратко: Несуществующий документ 999")["found"]


class FakeLLM:
    def __init__(self):
        self.prompt = None

    def status(self):
        return {"available": True, "model": "fake.gguf"}

    def generate(self, system, prompt, max_tokens=260):
        self.prompt = prompt
        return "Утверждено три бюджета [1] [2], крупнейший — отдел продаж [9]."


def test_llm_writes_summary_only():
    llm = FakeLLM()
    r = ask("Бюджеты", llm=llm)
    assert r["generated"] and r["llm"]["model"] == "fake.gguf"
    assert "[9]" not in r["summary"] and "[1]" in r["summary"]          # ссылка на несуществующий источник убрана
    assert r["table"]["total"] == 11_800_000                             # цифры считает не модель
    assert "8 650 000" in llm.prompt and "Общая сумма" in llm.prompt


def test_question_about_text_has_no_sums():
    idx, docs = setup()
    a = answer("сколько процентов неустойка за просрочку?", None, docs, idx, None, date(2025, 11, 10))
    assert a["found"] and "amount" not in a["table"]["columns"] and a["table"]["total"] is None
    assert "₽" not in a["headline"]
    # «сколько договоров» — по-прежнему счёт и суммы
    b = answer("сколько договоров", None, docs, idx, None, date(2025, 11, 10))
    assert "amount" in b["table"]["columns"]


def test_ask_one_document():
    idx, docs = setup()
    doc = next(d for d in docs if "124-А" in d["title"])
    a = answer("какая неустойка за просрочку?", None, [], idx, None, doc_id=doc["id"])
    assert a["found"] and a["kind"] == "doc" and not a["generated"]
    assert any("неустойка" in s["quote"] for s in a["sources"]) and all(s["block"] is not None for s in a["sources"])
    miss = answer("космодром", None, [], idx, None, doc_id=doc["id"])
    assert not miss["found"]

    class Llm:
        def status(self):
            return {"available": True, "model": "fake"}

        def generate(self, system, prompt, max_tokens=260):
            self.prompt = prompt
            return "Неустойка — 0,1 % в день [99]. В документе это не указано."

    llm = Llm()
    g = answer("какая неустойка за просрочку?", None, [], idx, llm, doc_id=doc["id"])
    assert g["generated"] and "[99]" not in g["summary"] and "не указано" not in g["summary"]
    assert "неустойка" in llm.prompt and g["sources"]


def test_tidy_not_stated():
    from app.assistant.engine import _tidy
    assert _tidy("в документе это не указано [1]") == "В документе это не указано."
    assert _tidy("Срок — 10 дней [2]. В документе это не указано.") == "Срок — 10 дней [2]."
    assert _tidy("Каркас состоит из меню и панели [1]. Также есть индикатор фоновых задач и прогресс импо") == "Каркас состоит из меню и панели [1]."




def test_matched_heading_brings_its_section():
    from app.assistant.engine import _fragments, _terms, _with_sections
    blocks = ["Регламент"] + ["Вводный абзац. " * 30] + ["1. Каркас окна и общие элементы", "Левое меню", "Логотип и пункты меню",
              "Верхняя панель", "2. Экран «Обзор»", "Стартовый экран со счётчиками"]
    frags = _with_sections(blocks, _fragments(blocks, _terms("из чего состоит каркас"), 8, 600))
    sec = next(f for f in frags if f.get("section"))
    assert sec["block"] == 2 and sec["quote"] == "1. Каркас окна и общие элементы"
    assert "Левое меню" in sec["text"] and "Верхняя панель" in sec["text"] and "Стартовый экран" not in sec["text"]




def test_outline_gives_every_section_a_number():
    from app.assistant.engine import _fragments, _terms, _with_outline, _with_sections
    blocks = ["Каталог"] + ["Вводный абзац про экраны. " * 20] + ["1. Каркас окна", "Левое меню", "2. Экран «Обзор»", "Счётчики",
              "3. Экран «Поиск»", "Строка поиска"]
    frags = _with_outline(blocks, _with_sections(blocks, _fragments(blocks, _terms("какие экраны"), 8, 600)))
    assert [f["block"] for f in frags] == sorted(f["block"] for f in frags)
    assert {2, 4, 6} <= {f["block"] for f in frags}                      # все заголовки на месте, каждый можно процитировать
    assert len({f["block"] for f in frags}) == len(frags)




def test_reference_ranges_and_heading_numbers():
    from app.assistant.engine import _clean_refs, _fix_heading_refs
    assert _clean_refs("Экраны [7–9], панели [2, 4] и ещё [12-99].", 9) == "Экраны [7][8][9], панели [2][4] и ещё ."
    frags = [{"n": 4, "outline": True, "quote": "2. Экран «Обзор»"}, {"n": 6, "section": True, "quote": "3. Экран «Поиск»"}, {"n": 2, "quote": None}]
    assert _fix_heading_refs("Есть 2. Экран «Обзор» [2] и экран «Поиск» [3]. Всего их семь [2].", frags) \
        == "Есть 2. Экран «Обзор» [4] и экран «Поиск» [6]. Всего их семь [2]."
    assert _fix_heading_refs("Также есть экран «Обзор», экран «Поиск» и прочее [7][8][9].", frags) == "Также есть экран «Обзор», экран «Поиск» и прочее [4][6]."

