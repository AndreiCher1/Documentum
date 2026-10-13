package com.docintell.exception;

/**
 * Исключение: документ с указанным ID не найден в базе данных.
 */
public class DocumentNotFoundException extends RuntimeException {

    public DocumentNotFoundException(Long id) {
        super("Документ с ID " + id + " не найден");
    }

    public DocumentNotFoundException(String message) {
        super(message);
    }
}

