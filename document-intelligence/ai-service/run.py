"""
Скрипт для удобного запуска AI-сервиса.

Вместо длинной команды:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Можно просто:
    python run.py
"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"Запуск AI Service на {settings.HOST}:{settings.PORT}")
    print(f"Документация API: http://localhost:{settings.PORT}/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )

