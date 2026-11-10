"""Тесты сверки документа с базой и разбора ответа модели в смысловой проверке."""

import os
import tempfile

from app.checks.blocks import parse_blocks
from app.checks.engine import check_html
from app.checks.rules import Context
from app.checks.semantic import parse_answer, semantic_check
from app.search.index import SearchIndex

CONTRACT = ("<h1>ДОГОВОР ПОСТАВКИ № 124-А</h1><p>г. Самара 21.07.2025</p>"
            "<p>ООО «Вектор Снаб» в лице директора Крылова Дмитрия Сергеевича и ООО «Северный Терминал» в лице "
            "генерального директора Ковалёва И. П. заключили договор.</p>"
            "<p>Цена договора составляет 1 250 000 (один миллион двести пятьдесят тысяч) рублей.</p>"
            "<p>Поставщик: ООО «Вектор Снаб», ИНН 7725123450, КПП 772501001, р/с 40702810900000001234.</p>"
            "<p>Покупатель: ООО «Северный Терминал»</p><p>ИНН 6311098769</p>")
INVOICE = ("<h1>СЧЁТ № 58</h1><p>10.09.2025</p><p>Поставщик: ООО «Вектор Снаб», ИНН 7707083893, КПП 772501001.</p>"
           "<p>Покупатель: ООО «Северный Терминал», ИНН 6311098769.</p>"
           "<p>Оплата по договору поставки № 124-А от 12.07.2025.</p>"
           "<p>Итого к оплате: 1 400 000 (один миллион четыреста тысяч) рублей.</p>")
ORDER = ("<h1>ПРИКАЗ № 7</h1><p>01.09.2025</p><p>ООО «Вектор Снаб» в лице директора Орлова Петра Ильича приказывает "
         "назначить ответственного.</p>")


def _index():
    idx = SearchIndex(os.path.join(tempfile.mkdtemp(), "search.db"))
    idx.upsert(1, "ДОГОВОР ПОСТАВКИ № 124-А", CONTRACT)
    idx.upsert(2, "СЧЁТ № 58", INVOICE)
    idx.upsert(3, "ПРИКАЗ № 7", ORDER)
    return idx


def _rules(result):
    return {f["rule"]: f for f in result["findings"]}


def test_invoice_against_contract():
    r = check_html(INVOICE, "INVOICE", doc_id=2, index=_index())
    f = _rules(r)
    assert f["cross-inn"]["quote"] == "7707083893" and f["cross-inn"]["source"]["docId"] == 1
    assert "7725123450" in f["cross-inn"]["why"] and f["cross-inn"]["category"] == "Сверка с базой"
    assert f["cross-ref-date"]["severity"] == "warning" and "21.07.2025" in f["cross-ref-date"]["why"]
    # сумма сверяется на том же месте (ссылка на договор) — замечание дописано к находке о дате
    assert "cross-ref-amount" not in f and "1 400 000" in f["cross-ref-date"]["why"] and "1 250 000" in f["cross-ref-date"]["why"]
    assert "cross-ref-party" not in f and r["cross"]["documents"] == 2
    # ИНН с неверной контрольной суммой: пометка одна (от правила), но сведения сверки в ней сохраняются
    bad = check_html(INVOICE.replace("7707083893", "7725123540"), "INVOICE", doc_id=2, index=_index())
    inn = _rules(bad)["inn"]
    assert "cross-inn" not in _rules(bad) and inn["source"]["docId"] == 1 and "7725123450" in inn["why"]
    # у покупателя ИНН тот же — замечаний нет
    assert sum(1 for x in r["findings"] if x["rule"] == "cross-inn") == 1


def test_head_changed_and_requisites_in_next_block():
    r = check_html(CONTRACT, "CONTRACT", doc_id=1, index=_index())
    head = _rules(r)["cross-head"]
    assert head["quote"] == "Крылова Дмитрия Сергеевича" and "Орлова" in head["why"] and head["severity"] == "warning"
    assert head["source"]["docId"] == 3 and head["source"]["block"] is not None
    # ИНН покупателя стоит в отдельном абзаце после названия — он всё равно привязан к организации
    from app.checks.cross import profile
    p = profile([b.text for b in parse_blocks(CONTRACT)[0]], "ДОГОВОР ПОСТАВКИ № 124-А")
    assert p["orgs"]["северный терминал"]["inn"]["value"] == "6311098769" and p["kind"] == "contract" and p["number"] == "124-а"


def test_no_cross_findings_without_other_documents():
    idx = SearchIndex(os.path.join(tempfile.mkdtemp(), "search.db"))
    idx.upsert(1, "ДОГОВОР", CONTRACT)
    idx.upsert(9, "Копия", CONTRACT)
    r = check_html(CONTRACT, "CONTRACT", doc_id=1, index=idx)
    assert not [f for f in r["findings"] if f["rule"].startswith("cross-")] and r["cross"]["documents"] == 0


RISKY = ("<p>3.1. Оплата производится в течение 10 рабочих дней.</p><p>3.2. Договор продлевается автоматически на тот же срок.</p>"
         "<p>5.2. Покупатель оплачивает товар в течение 30 календарных дней.</p><p>6.1. За просрочку начисляется неустойка 1 % в день.</p>")


class FakeLLM:
    def __init__(self, answer):
        self.answer, self.prompt = answer, None

    def status(self):
        return {"available": True, "model": "fake"}

    def generate(self, system, prompt, max_tokens=260):
        self.prompt = prompt
        return self.answer


def test_semantic_findings_are_anchored_to_text():
    llm = FakeLLM("ПРОТИВОРЕЧИЕ | 1 и 3 | в течение 10 рабочих дней | срок оплаты указан по-разному\n"
                  "РИСК | [4] | неустойка 1 % в день | у неустойки нет верхнего предела\n"
                  "РИСК | 9 | выдуманный фрагмент | такого номера нет в тексте вообще\n"
                  "РИСК | 2 | этой цитаты в тексте нет совсем | модель выдумала цитату целиком\n"
                  "Просто болтовня без формата")
    r = check_html(RISKY, "CONTRACT", llm=llm, deep=True)
    ai = [f for f in r["findings"] if f["ai"]]
    # риск про неустойку нашло и правило (оно важнее и точнее) — на этом месте остаётся одна пометка, от правила
    assert [f["rule"] for f in ai] == ["ai-contradiction"]
    assert ai[0]["quote"] == "в течение 10 рабочих дней" and ai[0]["block"] == 0 and "30 календарных дней" in ai[0]["why"]
    assert [f["rule"] for f in r["findings"] if f["block"] == 3] == ["risk-penalty"]
    assert r["semantic"] == {"available": True, "chunks": 1, "total": 1, "found": 2, "model": "fake"}
    assert "[3] 5.2. Покупатель" in llm.prompt
    # без deep модель не вызывается
    quiet = FakeLLM("РИСК | 1 | Оплата производится | что-то")
    assert check_html(RISKY, "CONTRACT", llm=quiet)["semantic"] is None and quiet.prompt is None


def test_semantic_without_model_and_quote_in_other_fragment():
    blocks, tables = parse_blocks(RISKY)
    assert semantic_check(Context(blocks=blocks, tables=tables), None)["available"] is False
    found = parse_answer("РИСК | 1 | продлевается автоматически | договор продлится без согласия сторон", blocks)
    assert len(found) == 1 and found[0].block == 1          # номер фрагмента перепутан — место найдено по цитате
    # «противоречие» без второго места или без чисел в обоих местах не принимается
    assert parse_answer("ПРОТИВОРЕЧИЕ | 2 | продлевается автоматически | одно мешает другому по смыслу", blocks) == []
    assert parse_answer("ПРОТИВОРЕЧИЕ | 2 и 3 | продлевается автоматически | одно мешает другому по смыслу", blocks) == []


def test_typical_risks_by_rules():
    html = ("<p>5.1. За просрочку оплаты начисляются пени в размере 10% от суммы задолженности за каждый день просрочки.</p>"
            "<p>5.2. За просрочку поставки — неустойка 0,1 % в день, но не более 10 % цены.</p>"
            "<p>6.1. Договор автоматически продлевается на тот же срок.</p>"
            "<p>6.2. Арендодатель вправе расторгнуть договор в одностороннем порядке.</p>"
            "<p>7.1. Недостатки устраняются в разумный срок.</p><p>7.2. Аванс при отказе Заказчика не возвращается.</p>")
    f = {x["rule"]: x for x in check_html(html, "CONTRACT")["findings"]}
    assert f["risk-penalty"]["severity"] == "warning" and "3650 % годовых" in f["risk-penalty"]["why"] and f["risk-penalty"]["quote"] == "10%"
    assert "risk-penalty-cap" not in f                       # у 0,1 % предел указан
    before = check_html("<p>В случае просрочки оплаты, за каждый просроченный день начисляется пени в размере 10% от суммы долга.</p>")
    assert [x["rule"] for x in before["findings"] if x["category"] == "Риски"] == ["risk-penalty"]
    assert {"risk-auto", "risk-unilateral", "risk-vague-term", "risk-no-refund"} <= set(f)
    assert all(x["category"] == "Риски" and not x["ai"] for r, x in f.items() if r.startswith("risk-"))
