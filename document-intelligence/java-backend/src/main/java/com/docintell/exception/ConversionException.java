package com.docintell.exception;

/**
 * Файл не удалось преобразовать для редактора (неподдерживаемый формат, пустой скан и т.п.).
 * Сообщение показывается пользователю как есть.
 */
public class ConversionException extends RuntimeException {
    public ConversionException(String message) {
        super(message);
    }
}
