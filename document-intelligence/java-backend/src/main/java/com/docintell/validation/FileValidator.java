package com.docintell.validation;

import com.docintell.exception.FileValidationException;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import java.util.Arrays;
import java.util.List;

/**
 * Валидатор загружаемых файлов: FileValidator
 *
 * БЕЗОПАСНОСТЬ:
 * Загрузка файлов пользователями — один из наиболее критичных векторов атак на веб-приложения.
 * Этот компонент реализует многоуровневую защиту:
 *
 * 1. Проверка на пустой файл (Empty Check) — предотвращает создание мусорных записей.
 * 2. Ограничение размера (Size Limit) — защита от атак типа Denial of Service (DoS переполнение диска).
 * 3. Защита от Path Traversal — предотвращает передачу вредоносных путей типа "../../windows/system32".
 * 4. Белый список расширений (Whitelist) — блокирует загрузку исполняемых скриптов (.exe, .sh, .jsp, .php).
 * 5. Проверка MIME-типа — удостоверяется, что формат соответствует документам или изображениям.
 */
@Component
public class FileValidator {

    private static final long MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 МБ

    private static final List<String> ALLOWED_EXTENSIONS = Arrays.asList(
            "pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp",
            "docx", "doc", "xlsx", "xls", "csv", "txt"
    );

    private static final List<String> ALLOWED_MIME_TYPES = Arrays.asList(
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/bmp",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "text/csv",
            "text/plain"
    );

    /**
     * Выполняет полную проверку загружаемого файла.
     *
     * @param file объект MultipartFile из HTTP-запроса
     * @throws FileValidationException если файл не прошёл валидацию
     */
    public void validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new FileValidationException("Загружаемый файл пуст или не был выбран.");
        }

        if (file.getSize() > MAX_FILE_SIZE_BYTES) {
            throw new FileValidationException("Размер файла превышает допустимый лимит 50 МБ.");
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || originalFilename.trim().isEmpty()) {
            throw new FileValidationException("Некорректное имя файла.");
        }

        // Защита от Path Traversal
        if (originalFilename.contains("..") || originalFilename.contains("/") || originalFilename.contains("\\")) {
            throw new FileValidationException("Подозрительное имя файла (обнаружены спецсимволы пути).");
        }

        // Проверка расширения по белому списку
        String extension = getFileExtension(originalFilename).toLowerCase();
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            throw new FileValidationException(
                    "Недопустимый формат файла: ." + extension +
                    ". Разрешены только: " + String.join(", ", ALLOWED_EXTENSIONS)
            );
        }

        // Проверка MIME-типа (если передан клиентом)
        String contentType = file.getContentType();
        if (contentType != null && !contentType.isBlank()) {
            boolean isAllowedMime = ALLOWED_MIME_TYPES.stream()
                    .anyMatch(mime -> contentType.toLowerCase().startsWith(mime));
            if (!isAllowedMime && !contentType.equals("application/octet-stream")) {
                throw new FileValidationException("Недопустимый MIME-тип содержимого: " + contentType);
            }
        }
    }

    public static String getFileExtension(String filename) {
        if (filename == null) return "";
        int lastDotIndex = filename.lastIndexOf('.');
        if (lastDotIndex > 0 && lastDotIndex < filename.length() - 1) {
            return filename.substring(lastDotIndex + 1);
        }
        return "";
    }
}

