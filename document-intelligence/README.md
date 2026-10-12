# 📄 Document Intelligence

Интеллектуальная система анализа и структурирования документов.

## Архитектура системы

```text
                    ПОЛЬЗОВАТЕЛЬ
                         │
                         ▼
                ┌─────────────────┐
                │     Electron    │
                │ HTML/CSS/JS     │
                │ Desktop UI      │ (порт 8080 опрашивает)
                └────────┬────────┘
                         │
                    REST / JSON
                         │
                         ▼
                ┌─────────────────┐
                │ Java / Spring   │
                │      Boot       │ (порт 8080)
                │ Backend API     │
                └───────┬─────────┘
                        │
             ┌──────────┴──────────┐
             │                     │
             ▼                     ▼
      ┌─────────────┐       ┌──────────────┐
      │ PostgreSQL  │       │ Python       │
      │   (этап 3)  │       │ FastAPI      │ (порт 8000)
      │  Database   │       │ AI Service   │
      └─────────────┘       └──────────────┘
```

---

## Структура проекта

```text
document-intelligence/
├── electron-app/       # Desktop клиент (Electron + HTML/CSS/JS)
├── java-backend/       # Главный сервер (Spring Boot 3, Java 21)
├── ai-service/         # Сервис компьютерного зрения и AI (FastAPI, Python)
├── docs/               # Архитектурная документация
└── .env.example        # Шаблон переменных окружения
```

---

## 🚀 Запуск Этапа 2 (Минимальный прототип)

### Шаг 1: Запуск Python AI Service

В первом терминале:
```powershell
cd "a:\Документум\Documentum\document-intelligence\ai-service"

# Создаём виртуальное окружение (один раз)
python -m venv venv

# Активируем его
.\venv\Scripts\Activate.ps1

# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем сервис
python run.py
```
Проверка в браузере: `http://localhost:8000/docs` или `http://localhost:8000/health`

---

### Шаг 2: Запуск Java Backend

Во втором терминале:
```powershell
cd "a:\Документум\Documentum\document-intelligence\java-backend"

# Сборка и запуск через Maven:
mvn spring-boot:run
```
Проверка в браузере: `http://localhost:8080/api/health`
(Java обратится к Python и вернёт общий статус системы).

---

### Шаг 3: Запуск Electron App

В третьем терминале:
```powershell
cd "a:\Документум\Documentum\document-intelligence\electron-app"

# Установка зависимостей (один раз)
npm install

# Запуск приложения
npm start
```

В открывшемся окне нажмите **«🔄 Проверить связь»** — вы увидите статус всех трёх компонентов!

