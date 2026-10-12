"""
Конфигурация AI-сервиса.

Используем pydantic-settings для загрузки настроек из переменных окружения.
Это позволяет:
- Не хардкодить пароли и адреса в коде
- Легко менять настройки для разных сред (dev, production)
- Автоматически читать из .env файла
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения, загружаемые из переменных окружения."""
    
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Максимальный размер файла (в байтах): 50 МБ
    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    
    # Допустимые MIME-типы
    ALLOWED_MIME_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/bmp",
        "application/pdf"
    ]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Создаём единственный экземпляр настроек
settings = Settings()

