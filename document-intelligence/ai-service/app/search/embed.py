"""
Модель «смысловых отпечатков» (эмбеддингов) — необязательная часть поиска.

Отпечаток — вектор чисел для абзаца: у близких по смыслу абзацев векторы похожи, даже если слова разные.
Модель — файл .gguf в папке ai-service/models/embed (или путь в DOCUMENTUM_EMBED_MODEL), считает на процессоре
через llama.cpp. Нет файла или библиотеки — поиск работает по словам и синонимам, как раньше.

Проверено на Qwen3-Embedding-0.6B (Q8, 640 МБ): ~0,16 с на абзац, верный абзац в первых трёх у 9 запросов из 10.
Маленькие модели (granite-107m, e5-small в GGUF) на русских документах оказались непригодны.
"""

from __future__ import annotations

import glob
import logging
import os
import threading
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

EMBED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models", "embed")
DIM = 256            # храним первые 256 чисел вектора (модель обучена так, чтобы начало вектора несло основной смысл)
MAX_CHARS = 1200     # длинный абзац обрезается: смысл обычно ясен из начала
QUERY_PREFIX = "Instruct: Given a search query, retrieve relevant passages that answer the query\nQuery: "


def find_embed_model() -> Optional[str]:
    path = os.environ.get("DOCUMENTUM_EMBED_MODEL")
    if path and os.path.isfile(path):
        return path
    files = sorted(glob.glob(os.path.join(EMBED_DIR, "*.gguf")))
    return files[0] if files else None


class Embedder:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._failed: Optional[str] = None

    @property
    def name(self) -> Optional[str]:
        """Имя модели — ключ кэша отпечатков: у другой модели векторы другие."""
        path = find_embed_model()
        return os.path.basename(path) if path else None

    def status(self) -> dict:
        import importlib.util
        path = find_embed_model()
        reason = None
        if self._failed:
            reason = self._failed
        elif importlib.util.find_spec("llama_cpp") is None:
            reason = "Не установлена библиотека llama-cpp-python"
        elif not path:
            reason = "Нет файла модели (.gguf) в папке ai-service/models/embed"
        return {"available": reason is None, "loaded": self._model is not None,
                "model": os.path.basename(path) if path else None, "reason": reason}

    def _load(self):
        if self._model is None and not self._failed:
            path = find_embed_model()
            try:
                from llama_cpp import Llama
                threads = max(2, min(4, (os.cpu_count() or 4) // 4))
                logger.info("Загружаю модель отпечатков %s (потоков: %s)", path, threads)
                # контекст и пакет по 512: при 1024 процесс занимал 1,5 ГБ вместо 0,95 ГБ, а абзац всё равно обрезается
                self._model = Llama(model_path=path, embedding=True, n_ctx=512, n_batch=512, n_threads=threads,
                                    use_mmap=False, verbose=False)
            except Exception as e:  # модель необязательна: любая ошибка — работаем без неё
                self._failed = f"Модель отпечатков не загрузилась: {e}"
                logger.error(self._failed, exc_info=True)
        return self._model

    def encode(self, texts: List[str], query: bool = False) -> Optional[np.ndarray]:
        """Векторы единичной длины, по строке на текст (float32, DIM чисел). None — модель недоступна."""
        if not self.status()["available"]:
            return None
        qwen = "qwen" in (self.name or "").lower()
        out = []
        with self._lock:
            model = self._load()
            if model is None:
                return None
            try:
                for text in texts:
                    text = " ".join(text.split())[:MAX_CHARS]
                    if query and qwen:
                        text = QUERY_PREFIX + text
                    v = np.asarray(model.embed(text, truncate=True), dtype=np.float32)
                    if v.ndim == 2:                 # модель без объединения — усредняем по словам
                        v = v.mean(axis=0)
                    v = v[:DIM]
                    out.append(v / (np.linalg.norm(v) or 1.0))
            except Exception as e:
                logger.error("Ошибка расчёта отпечатков: %s", e, exc_info=True)
                return None
        return np.vstack(out) if out else np.zeros((0, DIM), dtype=np.float32)


local_embedder = Embedder()
