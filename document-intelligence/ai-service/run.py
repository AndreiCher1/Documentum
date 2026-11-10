"""
Скрипт для удобного запуска AI-сервиса.

Автоматически определяет наличие локального виртуального окружения (venv)
и переключается на него, если скрипт запущен через глобальный Python.
"""

import os
import sys
import subprocess

# Защита от запуска через pythonw.exe (где stdout/stderr равны None)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Автоматическое переключение на venv, если запущен глобальный Python
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_py_name = "pythonw.exe" if "pythonw" in sys.executable.lower() else "python.exe"
venv_python = os.path.join(script_dir, "venv", "Scripts", venv_py_name)
if not os.path.exists(venv_python):
    venv_python = os.path.join(script_dir, "venv", "Scripts", "python.exe")

if sys.prefix == sys.base_prefix and os.path.exists(venv_python):
    result = subprocess.run([venv_python, os.path.abspath(__file__)] + sys.argv[1:])
    sys.exit(result.returncode)

# Поставка для покупателей: модели распознавания сканов лежат рядом с программой (runtime\paddlex),
# а не в профиле пользователя, — иначе при первом скане программа полезла бы за ними в интернет.
_bundled_ocr = os.path.join(os.path.dirname(os.path.dirname(script_dir)), "runtime", "paddlex")
if os.path.isdir(_bundled_ocr):
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", _bundled_ocr)

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False
    )
