package com.docintell.enums;

/**
 * Жизненный цикл обработки документа.
 *
 * UPLOADED   — Файл успешно загружен на сервер и сохранён на диске.
 * PROCESSING — Отправлен в Python AI-сервис, идёт распознавание и анализ.
 * COMPLETED  — Анализ завершён успешно, структурированные поля сохранены в БД.
 * FAILED     — В процессе распознавания или извлечения произошла ошибка.
 */
public enum AnalysisStatus {
    UPLOADED("Загружен"),
    PROCESSING("В обработке"),
    COMPLETED("Обработан"),
    FAILED("Ошибка обработки");

    private final String description;

    AnalysisStatus(String description) {
        this.description = description;
    }

    public String getDescription() {
        return description;
    }
}

