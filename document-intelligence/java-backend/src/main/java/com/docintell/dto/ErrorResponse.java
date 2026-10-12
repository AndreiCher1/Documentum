package com.docintell.dto;

import java.time.LocalDateTime;

/**
 * DTO для ошибок.
 *
 * Когда происходит ошибка, вместо стандартного Spring-ответа
 * с NullPointerException и стектрейсом, мы возвращаем
 * понятное сообщение для пользователя.
 */
public record ErrorResponse(
        int status,
        String error,
        String message,
        LocalDateTime timestamp
) {
    public static ErrorResponse of(int status, String error, String message) {
        return new ErrorResponse(status, error, message, LocalDateTime.now());
    }
}
