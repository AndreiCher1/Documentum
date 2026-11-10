"""Тесты поиска: стеммер, поля карточки, индекс BM25, синонимы, фрагменты, сохранение на диск."""

import os
import tempfile

from app.search.fields import extract_fields
from app.search.index import SearchIndex
from app.search.stemmer_ru import stem

CONTRACT = ("<h1>ДОГОВОР АРЕНДЫ № 15/25</h1><p>г. Самара    1 марта 2025 г.</p>"
            "<p>ООО «Склад-Сервис» и ООО «Северный Терминал» заключили договор.</p>"
            "<p>1.1. Арендная плата составляет 210 000 (двести десять тысяч) рублей в месяц.</p>"
            "<p>2.1. Договор действует до 28 февраля 2026 г.</p>"
            "<p>За просрочку платежа арендатор уплачивает пени 0,1 %.</p>"
            "<p>Арендодатель: ИНН 7725123450. Арендатор: ИНН 6311098769.</p>")
ORDER = ("<h1>ПРИКАЗ № 322</h1><p>27.11.2025</p><p>Утвердить бюджет отдела маркетинга на декабрь 2025 года "
         "в сумме 3 150 000 рублей.</p><p>Контроль оставляю за собой. Генеральный директор Ковалёв И. П.</p>")
MEMO = ("<h1>Служебная записка № 64</h1><p>05.11.2025</p><p>Прошу согласовать закупку ноутбуков для отдела продаж "
        "на сумму 245 000 рублей. Поставка до 20.12.2025. Поставщик — ИП Гусев Андрей Викторович.</p>")


def test_stemmer_forms():
    assert {stem(w) for w in ["договор", "договора", "договору", "договорами"]} == {"договор"}
    assert stem("аренды") == stem("аренда") == "аренд"
    assert stem("Утверждённые") == stem("утвержденный")


def test_extract_fields():
    f = extract_fields(CONTRACT)
    assert f["title"] == "ДОГОВОР АРЕНДЫ № 15/25"
    assert f["number"] == "15/25"
    assert f["date"] == "2025-03-01"
    assert f["counterparties"] == ["ООО «Склад-Сервис»", "ООО «Северный Терминал»"]
    assert f["amount"] == 210000
    assert f["validUntil"] == "2026-02-28"
    assert [i["value"] for i in f["inns"]] == ["7725123450", "6311098769"] and all(i["valid"] for i in f["inns"])
    o = extract_fields(ORDER)
    assert o["number"] == "322" and o["date"] == "2025-11-27" and o["amount"] == 3150000
    m = extract_fields(MEMO)
    assert m["counterparties"] == ["ИП Гусев Андрей Викторович"] and m["amount"] == 245000
    # число перед скобками — ещё не сумма: нужны число прописью и рубли рядом
    assert extract_fields("<p>Комната в 4 (четырёх) комнатной квартире, договор в 2 (двух) экземплярах.</p>")["amount"] is None
    assert extract_fields("<p>В приложении 7 основных экранов (см. раздел 2).</p>")["amount"] is None
    assert extract_fields("<p>Плата 5000 (пять тысяч) рублей в месяц.</p>")["amount"] == 5000


def _index():
    path = os.path.join(tempfile.mkdtemp(), "search.db")
    idx = SearchIndex(path)
    idx.upsert(1, "Договор аренды № 15/25", CONTRACT)
    idx.upsert(2, "Приказ № 322", ORDER)
    idx.upsert(3, "Служебная записка № 64", MEMO)
    return idx, path


def test_words_mode_morphology_and_and():
    idx, _ = _index()
    assert [r["id"] for r in idx.search("договоры аренды")] == [1]
    assert [r["id"] for r in idx.search("бюджета маркетинга")] == [2]
    assert idx.search("аренда маркетинг") == []                      # все слова обязательны
    assert [r["id"] for r in idx.search("15/25")] == [1]             # номер документа


def test_sem_mode_synonyms():
    idx, _ = _index()
    words = [r["id"] for r in idx.search("штраф", "words")]
    sem = idx.search("штраф", "sem")
    assert words == [] and [r["id"] for r in sem] == [1]             # «штраф» ~ «пени»
    assert sem[0]["exact"] is False
    assert [r["id"] for r in idx.search("покупка ноутбуков", "sem")] == [3]   # «покупка» ~ «закупка»


def test_snippet_highlights_and_filter():
    idx, _ = _index()
    r = idx.search("пени", "words")[0]
    s = r["snippets"][0]
    assert s["block"] == 5
    a, b = s["highlights"][0]
    assert s["text"][a:b] == "пени"
    assert idx.search("пени", "words", ids=[2, 3]) == []             # фильтр по документам


def test_persistence_and_sync():
    idx, path = _index()
    idx.remove(3)
    again = SearchIndex(path)
    assert sorted(again.docs) == [1, 2]
    assert [r["id"] for r in again.search("арендная плата")] == [1]
    assert again.keep_only([1]) == 1 and sorted(again.docs) == [1]



class FakeEmbedder:
    """Вместо модели: вектор зависит от «темы» текста. Считает, сколько абзацев его попросили обработать."""
    name = "fake"
    TOPICS = [("аренд", "плат", "жиль", "съем"), ("бюджет", "маркетинг"), ("ноутбук", "закупк", "компьютер"), ("пени", "просрочк")]

    def __init__(self):
        self.calls = 0

    def status(self):
        return {"available": True, "loaded": True, "model": self.name, "reason": None}

    def encode(self, texts, query=False):
        import numpy as np
        from app.search.embed import DIM
        out = np.zeros((len(texts), DIM), dtype=np.float32)
        for i, t in enumerate(texts):
            self.calls += 0 if query else 1
            low = t.lower()
            for k, words in enumerate(self.TOPICS):
                out[i, k] = sum(w in low for w in words)
            out[i, 101 if query else 100] = 0.1
            out[i] /= np.linalg.norm(out[i])
        return out


def test_block_embeddings_are_incremental():
    emb = FakeEmbedder()
    path = os.path.join(tempfile.mkdtemp(), "search.db")
    idx = SearchIndex(path, emb, background=False)
    idx.upsert(1, "Договор аренды № 15/25", CONTRACT)
    assert idx.embed_status()["pending"] == 7
    assert idx.embed_pending() == 7 and emb.calls == 7 and idx.embed_status()["pending"] == 0
    # изменён один абзац из семи — пересчитывается только он
    idx.upsert(1, "Договор аренды № 15/25", CONTRACT.replace("пени 0,1 %", "пени 0,5 %"))
    assert idx.embed_status()["pending"] == 1
    assert idx.embed_pending() == 1 and emb.calls == 8
    # тот же текст под другим номером (копия документа) — считать нечего
    idx.upsert(5, "Копия", CONTRACT.replace("пени 0,1 %", "пени 0,5 %"))
    assert idx.embed_status()["pending"] == 0 and idx.embed_pending() == 0 and emb.calls == 8
    # после перезапуска отпечатки берутся с диска
    again = SearchIndex(path, emb, background=False)
    assert again.embed_status()["pending"] == 0 and again.embed_status()["ready"] == 14
    # отпечатки абзацев, которых больше нет в документах, убираются при сверке
    again.keep_only([1, 5])
    assert again.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 7


def test_semantic_search_without_common_words():
    emb = FakeEmbedder()
    idx = SearchIndex(os.path.join(tempfile.mkdtemp(), "search.db"), emb, background=False)
    idx.upsert(1, "Договор аренды № 15/25", CONTRACT)
    idx.upsert(3, "Служебная записка № 64", MEMO)
    idx.embed_pending()
    assert idx.search("компьютер", "words") == []
    hit = idx.search("компьютер", "sem")
    assert [r["id"] for r in hit] == [3] and hit[0]["snippets"][0]["semantic"] and "ноутбуков" in hit[0]["snippets"][0]["text"]
    assert idx.search("космодром", "sem") == []

