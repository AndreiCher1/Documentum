"""
Скрипт для удобного запуска AI-сервиса.

Автоматически определяет наличие локального виртуального окружения (venv)
и переключается на него, если скрипт запущен через глобальный Python.
"""

import os
import sys
import subprocess

# Автоматическое переключение на venv, если запущен глобальный Python
script_dir = os.path.dirname(os.path.abspath(__file__))
venv_python = os.path.join(script_dir, "venv", "Scripts", "python.exe")

if sys.prefix == sys.base_prefix and os.path.exists(venv_python):
    print(f"Используем виртуальное окружение: {venv_python}")
    result = subprocess.run([venv_python, os.path.abspath(__file__)] + sys.argv[1:])
    sys.exit(result.returncode)

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"Запуск AI Service на {settings.HOST}:{settings.PORT}")
    print(f"Документация API: http://localhost:{settings.PORT}/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False
    )
