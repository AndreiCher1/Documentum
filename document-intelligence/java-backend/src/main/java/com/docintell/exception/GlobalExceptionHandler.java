package com.docintell.exception;

import com.docintell.dto.ErrorResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

/**
 * Глобальный обработчик ошибок.
 *
 * @RestControllerAdvice — говорит Spring:
 * "Если в любом контроллере произошла ошибка — обработай её здесь."
 *
 * Без этого класса при ошибке пользователь увидит:
 *   500 Internal Server Error + стектрейс Java
 *
 * С этим классом пользователь увидит:
 *   {"status": 500, "error": "Внутренняя ошибка", "message": "Понятное описание"}
 *
 * Аналогия: это как "служба поддержки" — перехватывает все проблемы
 * и переводит их на понятный язык.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger logger = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ErrorResponse> handleMaxUploadSize(MaxUploadSizeExceededException e) {
        logger.warn("Файл слишком большой: {}", e.getMessage());
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(ErrorResponse.of(
                        400,
                        "Файл слишком большой",
                        "Максимальный размер файла: 50 МБ"
                ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception e) {
        logger.error("Непредвиденная ошибка: {}", e.getMessage(), e);
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ErrorResponse.of(
                        500,
                        "Внутренняя ошибка сервера",
                        "Произошла непредвиденная ошибка. Попробуйте ещё раз."
                ));
    }
}
