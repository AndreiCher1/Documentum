package com.docintell.dto;

import java.time.LocalDateTime;

/**
 * DTO (Data Transfer Object) для ответа о состоянии системы.
 *
 * DTO — это объект, который используется ТОЛЬКО для передачи данных
 * между слоями приложения или через API.
 *
 * Почему не использовать Entity напрямую?
 * - Entity привязан к базе данных и может содержать лишние данные
 * - DTO позволяет контролировать, какие именно данные отправляются клиенту
 * - Безопасность: мы не раскрываем внутреннюю структуру БД
 *
 * Аналогия: Entity — это полная медицинская карта, а DTO — это выписка
 * только с теми данными, которые нужны конкретному получателю.
 */
public record HealthStatusResponse(
        String status,
        String javaBackend,
        AiServiceStatus aiService,
        String database,
        LocalDateTime timestamp
) {
    /**
     * record — это компактный способ создать класс с полями в Java 16+.
     * Он автоматически создаёт конструктор, getter-ы, equals(), hashCode(), toString().
     *
     * Вместо 50 строк кода с полями, геттерами и конструктором —
     * одна строка с record.
     */

    public record AiServiceStatus(
            String status,
            @com.fasterxml.jackson.annotation.JsonProperty("models_loaded")
            boolean modelsLoaded,
            @com.fasterxml.jackson.annotation.JsonProperty("ocr_ready")
            boolean ocrReady,
            String version
    ) {}
}
