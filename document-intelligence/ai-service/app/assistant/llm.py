"""
Локальная языковая модель (llama.cpp) — необязательная часть ассистента.

Модель — файл .gguf в папке ai-service/models (или путь в переменной DOCUMENTUM_LLM_MODEL).
Если библиотеки llama-cpp-python или файла модели нет, сервис работает без неё:
ассистент отвечает точными фактами из карточек и поиска, только без «живой» формулировки.

Модель загружается при первом вопросе (а не при старте), считает на процессоре.
"""

from __future__ import annotations

import glob
import logging
import os
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "models")


def find_model() -> Optional[str]:
    path = os.environ.get("DOCUMENTUM_LLM_MODEL")
    if path and os.path.isfile(path):
        return path
    files = sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))
    return files[0] if files else None


def _library_installed() -> bool:
    import importlib.util
    return importlib.util.find_spec("llama_cpp") is not None


class LocalLLM:
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._failed: Optional[str] = None

    def status(self) -> dict:
        path = find_model()
        library = _library_installed()
        reason = None
        if self._failed:
            reason = self._failed
        elif not library:
            reason = "Не установлена библиотека llama-cpp-python"
        elif not path:
            reason = "Нет файла модели (.gguf) в папке ai-service/models"
        return {"available": reason is None, "loaded": self._model is not None,
                "model": os.path.basename(path) if path else None, "reason": reason}

    def _load(self):
        if self._model is None and not self._failed:
            path = find_model()
            try:
                from llama_cpp import Llama
                threads = max(2, min(8, (os.cpu_count() or 4) // 2))
                logger.info("Загружаю языковую модель %s (потоков: %s)", path, threads)
                # use_mmap=False: файл читается в память один раз. С отображением файла (mmap) на Windows
                # процесс занимал 4,7 ГБ вместо 3,1 ГБ при той же скорости (замер на Qwen3-4B Q4, контекст 4096).
                self._model = Llama(model_path=path, n_ctx=int(os.environ.get("DOCUMENTUM_LLM_CTX", "4096")),
                                    n_threads=threads, use_mmap=False, verbose=False)
            except Exception as e:  # модель необязательна: любая ошибка — работаем без неё
                self._failed = f"Модель не загрузилась: {e}"
                logger.error(self._failed, exc_info=True)
        return self._model

    def generate(self, system: str, prompt: str, max_tokens: int = 260) -> Optional[str]:
        if not self.status()["available"]:
            return None
        with self._lock:                      # одна генерация за раз: модель занимает все выделенные потоки
            model = self._load()
            if model is None:
                return None
            try:
                # Qwen3 по умолчанию «размышляет» вслух — для коротких сводок это лишнее время
                if "qwen3" in os.path.basename(find_model() or "").lower():
                    prompt += " /no_think"
                out = model.create_chat_completion(
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                    max_tokens=max_tokens, temperature=0.2, top_p=0.9)
                text = out["choices"][0]["message"]["content"] or ""
            except Exception as e:
                logger.error("Ошибка генерации: %s", e, exc_info=True)
                return None
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        return text or None


local_llm = LocalLLM()
