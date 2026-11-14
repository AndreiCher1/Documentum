"""Запуск правил проверки над HTML документа."""

from __future__ import annotations

import logging
import re
import time
from typing import List

from app.checks.blocks import parse_blocks
from app.checks.rules import RULES, Context, Finding, POINT

logger = logging.getLogger(__name__)
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _where(f: Finding, ctx: Context) -> str:
    if f.block is None:
        return "документ в целом"
    b = ctx.blocks[f.block]
    if b.table is not None:
        return f"таблица {b.table + 1}, строка {b.row + 1}"
    m = POINT.match(b.text)
    if m:
        return f"п. {m.group(1)}"
    for prev in reversed(ctx.blocks[: f.block + 1]):
        if prev.tag in ("h1", "h2", "h3"):
            title = prev.text.strip()
            return "заголовок" if prev is b else f"раздел «{title[:40]}{'…' if len(title) > 40 else ''}»"
    return "начало документа" if f.block < 3 else f"абзац {f.block + 1}"


def check_html(html: str, document_type: str = "", doc_id=None, index=None, llm=None, deep: bool = False) -> dict:
    """index и doc_id — для сверки с остальными документами базы; llm и deep — смысловая проверка моделью."""
    started = time.time()
    blocks, tables = parse_blocks(html)
    ctx = Context(blocks=blocks, tables=tables, document_type=(document_type or "").upper())
    # нумерация должна отработать раньше ссылок — она собирает список существующих пунктов
    for rule in RULES:
        try:
            rule(ctx)
        except Exception as e:                      # одно сломанное правило не роняет всю проверку
            logger.error(f"Правило {rule.__name__} упало: {e}", exc_info=True)
    cross = None
    if index is not None and doc_id is not None:
        try:
            from app.checks.cross import cross_check
            cross = cross_check(ctx, doc_id, index)
        except Exception as e:
            logger.error(f"Сверка с базой упала: {e}", exc_info=True)
    semantic = None
    if deep:
        try:
            from app.checks.semantic import semantic_check
            semantic = semantic_check(ctx, llm)
        except Exception as e:
            logger.error(f"Смысловая проверка упала: {e}", exc_info=True)
            semantic = {"available": False, "chunks": 0, "total": 0, "found": 0}

    # пересекающиеся пометки в одном блоке не поставить — оставляем более важную
    kept: List[Finding] = []
    ranges = {}
    for f in sorted(ctx.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.block or 0, f.start or 0)):
        if f.block is not None and f.start is not None:
            taken = ranges.setdefault(f.block, [])
            clash = next((k for k in kept if k.block == f.block and k.start is not None and f.start < k.end and k.start < f.end), None)
            if clash is not None:
                # на одном месте две находки — пометку ставим одну, но сведения сверки с базой не теряем
                if f.source:
                    clash.source = clash.source or f.source
                    clash.why += " " + f.why
                continue
            taken.append((f.start, f.end))
        f.where = _where(f, ctx)
        kept.append(f)

    out = []
    for i, f in enumerate(sorted(kept, key=lambda f: (SEVERITY_ORDER[f.severity], f.block if f.block is not None else -1, f.start or 0)), 1):
        d = f.to_dict()
        d["id"] = f"f{i}"
        out.append(d)
    counts = {s: sum(1 for f in out if f["severity"] == s) for s in ("critical", "warning", "info")}
    return {"findings": out, "counts": counts, "blocks": len(blocks), "elapsedMs": round((time.time() - started) * 1000),
            "cross": cross, "semantic": semantic}
