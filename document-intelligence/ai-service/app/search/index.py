"""
Полнотекстовый индекс документов с русской морфологией и ранжированием BM25.

Хранение — SQLite (стандартная библиотека), в памяти — обратный индекс «основа → документы».
Режимы:
- words: в документе должны быть все слова запроса (в любой форме);
- sem:   слова запроса расширяются синонимами деловой лексики, достаточно части совпадений.
Результат содержит фрагменты с подсветкой и номер блока — редактор открывает документ на этом месте.

Смысловые отпечатки (если подключена модель, см. embed.py) считаются по абзацам и хранятся в таблице chunks
по контрольной сумме текста абзаца. Поэтому при сохранении документа пересчитываются только изменённые абзацы,
а одинаковые абзацы разных документов (копии, типовые пункты) считаются один раз. Расчёт идёт в фоне:
поиск по словам доступен сразу, смысловой — по мере готовности отпечатков.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional

import numpy as np

from app.checks.blocks import parse_blocks
from app.search.stemmer_ru import stem, tokens

logger = logging.getLogger(__name__)

STOP = {stem(w) for w in "и в во на по с со о об к ко за для от до не ни что это как все так же бы ли или а но из у при без над под".split()}

# Группы близких по смыслу слов деловых документов (основы)
SYNONYM_GROUPS = [
    ["аренд", "наем", "найм", "арендатор", "арендодател", "помещен"],
    ["неустойк", "пен", "штраф", "санкц"],
    ["оплат", "платеж", "расчет", "перечислен", "предоплат"],
    ["договор", "контракт", "соглашен"],
    ["руководител", "директор", "генеральн"],
    ["сотрудник", "работник", "персонал", "штат"],
    ["бюджет", "смет", "лимит"],
    ["поставк", "отгрузк", "доставк"],
    ["просрочк", "нарушен", "задержк", "опоздан"],
    ["расторжен", "прекращен"],
    ["приемк", "сдач", "акт"],
    ["ремонт", "подряд", "строительн"],
    ["закупк", "приобретен", "покупк"],
    ["охран", "безопасн"],
    ["претенз", "жалоб", "рекламац"],
    ["срок", "период"],
]
SYNONYMS: Dict[str, List[str]] = {}
for group in SYNONYM_GROUPS:
    for s in group:
        SYNONYMS.setdefault(s, []).extend(x for x in group if x != s)


def _chunk_hash(text: str) -> Optional[str]:
    """Контрольная сумма абзаца — ключ его отпечатка. Слишком короткие абзацы (номера, подписи) пропускаются."""
    text = " ".join(text.split())
    if len(text) < 8 or not any(ch.isalpha() for ch in text):
        return None
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:24]


def _expand(s: str) -> List[str]:
    """Синонимы для основы: точное совпадение группы или общее начало (неустойк ~ неустойкам)."""
    out = SYNONYMS.get(s, [])
    if not out:
        for k, v in SYNONYMS.items():
            if len(s) >= 4 and (s.startswith(k) or k.startswith(s)):
                out = v + [k]
                break
    return out


class SearchIndex:
    K1, B = 1.5, 0.75
    # Версия правил разбора (блоки, поля карточки). При смене индекс очищается: сервер данных при сверке
    # увидит, что документов нет, пришлёт их заново и заодно пересчитает поля карточек (сумма, дата и т.д.).
    VERSION = 2
    TITLE_WEIGHT = 3
    SIM_MIN = 0.5          # с такой близости абзац считается подходящим по смыслу (калибровано на Qwen3-Embedding)
    EMBED_BATCH = 4        # абзацев за один заход фонового расчёта — чтобы поиск не ждал долго

    def __init__(self, path: str, embedder=None, background: bool = True):
        self.path = path
        self.embedder = embedder
        self.background = background
        self.queue: List[int] = []          # документы, у которых есть абзацы без отпечатка
        self.worker: Optional[threading.Thread] = None
        self.computed = 0                   # сколько отпечатков посчитано с запуска (остальные взяты готовыми)
        self.qcache: Dict[str, np.ndarray] = {}
        self.lock = threading.RLock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS docs (id INTEGER PRIMARY KEY, title TEXT, blocks TEXT, tf TEXT, length INTEGER)")
        self.db.execute("CREATE TABLE IF NOT EXISTS chunks (hash TEXT, model TEXT, vec BLOB, PRIMARY KEY (hash, model))")
        if self.db.execute("PRAGMA user_version").fetchone()[0] != self.VERSION:
            self.db.execute("DELETE FROM docs")
            self.db.execute(f"PRAGMA user_version = {self.VERSION}")
        self.db.commit()
        self.docs: Dict[int, dict] = {}
        self.postings: Dict[str, Dict[int, int]] = defaultdict(dict)
        for row in self.db.execute("SELECT id, title, blocks, tf, length FROM docs"):
            self._load(row[0], row[1], json.loads(row[2]), json.loads(row[3]), row[4])
        for doc_id in list(self.docs):
            self._attach_vectors(doc_id)
        self._kick()

    def _load(self, doc_id, title, blocks, tf, length):
        self.docs[doc_id] = {"title": title, "blocks": blocks, "tf": tf, "length": length,
                             "hashes": [_chunk_hash(b) for b in blocks], "vec": None, "has": None}
        for s, n in tf.items():
            self.postings[s][doc_id] = n

    # ------------------------------------------------------------------ смысловые отпечатки абзацев
    def _model(self) -> Optional[str]:
        return self.embedder.name if self.embedder is not None and self.embedder.status()["available"] else None

    def _attach_vectors(self, doc_id: int) -> int:
        """Подставляет документу готовые отпечатки из кэша. Возвращает, скольким абзацам отпечатка не хватило."""
        model = self._model()
        doc = self.docs.get(doc_id)
        if not model or not doc:
            return 0
        from app.search.embed import DIM
        hashes = doc["hashes"]
        want = sorted({h for h in hashes if h})
        found = {}
        for i in range(0, len(want), 400):
            part = want[i:i + 400]
            marks = ",".join("?" * len(part))
            for h, blob in self.db.execute(f"SELECT hash, vec FROM chunks WHERE model = ? AND hash IN ({marks})", [model] + part):
                found[h] = np.frombuffer(blob, dtype=np.float16)
        vec = np.zeros((len(hashes), DIM), dtype=np.float16)
        has = np.zeros(len(hashes), dtype=bool)
        for i, h in enumerate(hashes):
            if h in found and found[h].shape[0] == DIM:
                vec[i], has[i] = found[h], True
        doc["vec"], doc["has"] = vec, has
        missing = sum(1 for i, h in enumerate(hashes) if h and not has[i])
        if missing and doc_id not in self.queue:
            self.queue.append(doc_id)
        return missing

    def _kick(self) -> None:
        if self.background and self.queue and (self.worker is None or not self.worker.is_alive()):
            self.worker = threading.Thread(target=self.embed_pending, name="embed-index", daemon=True)
            self.worker.start()

    def embed_pending(self) -> int:
        """Считает отпечатки для абзацев, у которых их ещё нет. Возвращает число посчитанных."""
        done = 0
        while True:
            with self.lock:
                model = self._model()
                if not model or not self.queue:
                    return done
                doc_id = self.queue[0]
                doc = self.docs.get(doc_id)
                todo = []
                if doc is not None and doc["has"] is not None:
                    seen = set()
                    for i, h in enumerate(doc["hashes"]):
                        if h and not doc["has"][i] and h not in seen:
                            seen.add(h)
                            todo.append((h, doc["blocks"][i]))
                if not todo:
                    self.queue.pop(0)
                    continue
                batch = todo[:self.EMBED_BATCH]
            vecs = self.embedder.encode([t for _, t in batch])       # долгий расчёт — без блокировки индекса
            if vecs is None:
                with self.lock:
                    self.queue.clear()
                return done
            with self.lock:
                self.db.executemany("REPLACE INTO chunks VALUES (?, ?, ?)",
                                    [(h, model, v.astype(np.float16).tobytes()) for (h, _), v in zip(batch, vecs)])
                self.db.commit()
                self.computed += len(batch)
                done += len(batch)
                fresh = {h: v for (h, _), v in zip(batch, vecs)}
                for d in self.docs.values():                          # тот же абзац может быть в других документах
                    if d["has"] is None:
                        continue
                    for i, h in enumerate(d["hashes"]):
                        if h in fresh and not d["has"][i]:
                            d["vec"][i], d["has"][i] = fresh[h], True

    def query_vec(self, text: str) -> Optional[np.ndarray]:
        """Отпечаток запроса (с небольшим кэшем: уточняющие вопросы повторяют текст)."""
        text = " ".join((text or "").split())
        if not text or not self._model():
            return None
        if text not in self.qcache:
            v = self.embedder.encode([text], query=True)
            if v is None:
                return None
            if len(self.qcache) > 200:
                self.qcache.clear()
            self.qcache[text] = v[0]
        return self.qcache[text]

    def block_sims(self, doc_id: int, qvec: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """Близость запроса к каждому абзацу документа (0 — отпечатка ещё нет). None — смысловой поиск недоступен."""
        doc = self.docs.get(doc_id)
        if qvec is None or not doc or doc["vec"] is None or not doc["has"].any():
            return None
        return (doc["vec"].astype(np.float32) @ qvec) * doc["has"]

    def embed_status(self) -> dict:
        """Состояние смыслового индекса для экрана настроек."""
        st = self.embedder.status() if self.embedder is not None else {"available": False, "loaded": False, "model": None,
                                                                         "reason": "Модель отпечатков не подключена"}
        with self.lock:
            total = sum(1 for d in self.docs.values() for h in d["hashes"] if h)
            ready = sum(int(d["has"].sum()) for d in self.docs.values() if d["has"] is not None)
            return {**st, "blocks": total, "ready": ready, "pending": total - ready if st["available"] else 0, "computed": self.computed}

    # ------------------------------------------------------------------ запись
    def upsert(self, doc_id: int, title: str, html: str) -> None:
        blocks = [b.text for b in parse_blocks(html)[0]]
        tf = Counter()
        for s, _, _ in tokens(title or ""):
            tf[s] += self.TITLE_WEIGHT
        for text in blocks:
            for s, _, _ in tokens(text):
                tf[s] += 1
        length = sum(tf.values())
        with self.lock:
            self._remove_mem(doc_id)
            self._load(doc_id, title, blocks, dict(tf), length)
            self.db.execute("REPLACE INTO docs VALUES (?, ?, ?, ?, ?)",
                            (doc_id, title, json.dumps(blocks, ensure_ascii=False), json.dumps(tf, ensure_ascii=False), length))
            self.db.commit()
            # отпечатки неизменённых абзацев берутся готовыми, в очередь на расчёт идут только новые и изменённые
            self._attach_vectors(doc_id)
            self._kick()

    def remove(self, doc_id: int) -> None:
        with self.lock:
            self._remove_mem(doc_id)
            self.db.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
            self.db.commit()

    def keep_only(self, ids: Iterable[int]) -> int:
        """Удаляет из индекса документы, которых больше нет в базе. Возвращает число удалённых."""
        keep = set(ids)
        stale = [d for d in list(self.docs) if d not in keep]
        for d in stale:
            self.remove(d)
        with self.lock:                      # заодно убираем отпечатки абзацев, которых больше нет ни в одном документе
            used = {h for d in self.docs.values() for h in d["hashes"] if h}
            dead = [(h,) for (h,) in self.db.execute("SELECT DISTINCT hash FROM chunks") if h not in used]
            if dead:
                self.db.executemany("DELETE FROM chunks WHERE hash = ?", dead)
                self.db.commit()
        return len(stale)

    def _remove_mem(self, doc_id: int) -> None:
        old = self.docs.pop(doc_id, None)
        if old:
            for s in old["tf"]:
                self.postings[s].pop(doc_id, None)

    # ------------------------------------------------------------------ поиск
    def search(self, query: str, mode: str = "words", ids: Optional[Iterable[int]] = None, limit: int = 50) -> List[dict]:
        q = [s for s, _, _ in tokens(query) if s not in STOP]
        q = list(dict.fromkeys(q))
        if not q:
            return []
        allowed = set(ids) if ids is not None else None
        qvec = self.query_vec(query) if mode == "sem" else None
        with self.lock:
            n_docs = max(1, len(self.docs))
            avg = sum(d["length"] for d in self.docs.values()) / n_docs if self.docs else 1
            weights: Dict[str, float] = {s: 1.0 for s in q}
            groups = {s: [s] for s in q}
            if mode == "sem":
                for s in q:
                    for syn in _expand(s):
                        if syn not in weights:
                            weights[syn] = 0.6
                            groups[s].append(syn)

            scores: Dict[int, float] = defaultdict(float)
            for term, w in weights.items():
                post = self.postings.get(term)
                if not post:
                    continue
                idf = math.log(1 + (n_docs - len(post) + 0.5) / (len(post) + 0.5))
                for d, f in post.items():
                    if allowed is not None and d not in allowed:
                        continue
                    L = self.docs[d]["length"]
                    scores[d] += w * idf * f * (self.K1 + 1) / (f + self.K1 * (1 - self.B + self.B * L / avg))

            results = []
            for d, score in scores.items():
                tf = self.docs[d]["tf"]
                exact_hits = sum(1 for s in q if s in tf)
                group_hits = sum(1 for s in q if any(g in tf for g in groups[s]))
                if mode == "words" and exact_hits < len(q):
                    continue
                if mode == "sem" and group_hits < math.ceil(len(q) / 2):
                    continue
                results.append({"id": d, "score": round(score, 4), "exact": exact_hits == len(q),
                                "snippets": self._snippets(d, set(weights))})
            if qvec is not None:
                self._add_semantic(results, qvec, allowed)
            top = max((r["score"] for r in results), default=0) or 1
            results.sort(key=lambda r: (-r["exact"], -(0.5 * r["score"] / top + r.get("sim", 0))))
            return results[:limit]

    def _add_semantic(self, results: List[dict], qvec: np.ndarray, allowed) -> None:
        """Дополняет результаты: документы и абзацы, близкие к запросу по смыслу, даже без общих слов."""
        by_id = {r["id"]: r for r in results}
        for d, doc in self.docs.items():
            if allowed is not None and d not in allowed:
                continue
            sims = self.block_sims(d, qvec)
            if sims is None:
                continue
            i = int(sims.argmax())
            sim = float(sims[i])
            if sim < self.SIM_MIN:
                continue
            text = doc["blocks"][i].strip()
            snippet = {"block": i, "text": text[:220], "prefix": False, "suffix": len(text) > 220, "highlights": [],
                       "start": None, "end": None, "rank": 0, "semantic": True}
            r = by_id.get(d)
            if r is None:
                results.append({"id": d, "score": 0.0, "exact": False, "sim": round(sim, 3), "snippets": [snippet]})
            else:
                r["sim"] = round(sim, 3)
                if all(sn["block"] != i for sn in r["snippets"]):       # лучший по смыслу абзац — первым по важности
                    for sn in r["snippets"]:
                        sn["rank"] = sn.get("rank", 0) + 1
                    r["snippets"] = sorted(r["snippets"] + [snippet], key=lambda sn: sn["block"])

    def _snippets(self, doc_id: int, terms: set, max_snippets: int = 2, width: int = 220) -> List[dict]:
        blocks = self.docs[doc_id]["blocks"]
        scored = []
        for i, text in enumerate(blocks):
            hits = [(a, b) for s, a, b in tokens(text) if s in terms]
            if hits:
                distinct = len({text[a:b].lower() for a, b in hits})
                scored.append((distinct, len(hits), i, hits))
        scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
        out = []
        for rank, (_, _, i, hits) in enumerate(scored[:max_snippets]):
            text = blocks[i]
            first = hits[0][0]
            start = max(0, min(first - 60, len(text) - width))
            if start > 0:
                sp = text.find(" ", start)
                start = sp + 1 if 0 <= sp < first else start
            end = min(len(text), start + width)
            snippet = text[start:end]
            marks = [(a - start, b - start) for a, b in hits if a >= start and b <= end]
            out.append({"block": i, "text": snippet, "prefix": start > 0, "suffix": end < len(text),
                        "highlights": marks, "start": hits[0][0], "end": hits[0][1], "rank": rank})
        out.sort(key=lambda s: s["block"])
        return out

    def stats(self) -> dict:
        with self.lock:
            return {"documents": len(self.docs), "terms": len(self.postings)}
