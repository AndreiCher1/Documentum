package com.docintell.exception;

/**
 * Исключение: ошибка валидации загружаемого файла.
 * Выбрасывается, если файл пустой, превышает лимит размера,
 * имеет недопустимое расширение или потенциально опасное имя.
 */
public class FileValidationException extends RuntimeException {

    public FileValidationException(String message) {
        super(message);
    }
}

