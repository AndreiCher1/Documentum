"""
Разбор HTML редактора на абзацы (блоки).

Блок — элемент h1, h2, h3, p, li, td или th, который не вложен в другой такой элемент.
Редактор нумерует блоки точно так же (querySelectorAll + отбрасывание вложенных),
поэтому находка «блок 12, символы 30–41» попадает в то же место текста.
Текст блока совпадает с textContent в браузере: теги и <br> не дают символов, сущности раскрыты.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional

BLOCK_TAGS = {"h1", "h2", "h3", "p", "li", "td", "th"}
VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "col", "wbr"}


@dataclass
class Block:
    index: int
    tag: str
    text: str = ""
    table: Optional[int] = None      # номер таблицы, если блок — ячейка
    row: Optional[int] = None
    col: Optional[int] = None


@dataclass
class Table:
    rows: List[List[int]] = field(default_factory=list)   # индексы блоков-ячеек по строкам


class _Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: List[Block] = []
        self.tables: List[Table] = []
        self.stack: List[str] = []
        self.current: Optional[Block] = None
        self.current_depth = 0
        self.table_stack: List[int] = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        if tag == "table":
            self.tables.append(Table())
            self.table_stack.append(len(self.tables) - 1)
        elif tag == "tr" and self.table_stack and self.current is None:
            self.tables[self.table_stack[-1]].rows.append([])
        self.stack.append(tag)
        if tag in BLOCK_TAGS and self.current is None:
            b = Block(index=len(self.blocks), tag=tag)
            if tag in ("td", "th") and self.table_stack:
                t = self.tables[self.table_stack[-1]]
                if not t.rows:
                    t.rows.append([])
                b.table, b.row, b.col = self.table_stack[-1], len(t.rows) - 1, len(t.rows[-1])
                t.rows[-1].append(b.index)
            self.blocks.append(b)
            self.current = b
            self.current_depth = len(self.stack)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or tag not in self.stack:
            return
        # закрываем всё до парного тега (терпимо к неаккуратному HTML)
        while self.stack:
            top = self.stack.pop()
            if self.current is not None and len(self.stack) < self.current_depth:
                self.current = None
            if top == tag:
                break
        if tag == "table" and self.table_stack:
            self.table_stack.pop()

    def handle_data(self, data):
        if self.current is not None:
            self.current.text += data


def parse_blocks(html: str):
    p = _Parser()
    p.feed(html or "")
    p.close()
    return p.blocks, p.tables
