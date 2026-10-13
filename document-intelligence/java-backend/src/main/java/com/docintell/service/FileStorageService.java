package com.docintell.service;

import com.docintell.exception.FileValidationException;
import com.docintell.validation.FileValidator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.net.MalformedURLException;
import java.nio.file.*;
import java.util.UUID;

/**
 * Сервис файлового хранилища: FileStorageService
 *
 * ОТВЕЧАЕТ ЗА:
 * 1. Сохранение бинарного содержимого файлов на диск.
 * 2. Генерацию уникальных псевдонимов (UUID) для файлов, чтобы избежать коллизий имён.
 * 3. Безопасное чтение файлов для превью и скачивания.
 * 4. Удаление файлов при удалении документа из базы.
 *
 * ПОЧЕМУ ФАЙЛЫ ХРАНЯТСЯ НА ДИСКЕ, А НЕ В БАЗЕ (BLOB)?
 * - Базы данных не оптимизированы для хранения сотен мегабайт бинарных данных.
 * - Хранение файлов на диске позволяет операционной системе эффективно кешировать I/O.
 * - Python AI-сервис может быстро читать файлы напрямую или через streaming.
 * - Резервные копии базы данных (pg_dump) остаются компактными и быстрыми.
 */
@Service
public class FileStorageService {

    private static final Logger logger = LoggerFactory.getLogger(FileStorageService.class);

    private final Path storageDirectory;

    public FileStorageService(@Value("${file.upload-dir:./uploads}") String uploadDir) {
        this.storageDirectory = Paths.get(uploadDir).toAbsolutePath().normalize();
        try {
            Files.createDirectories(this.storageDirectory);
            logger.info("Каталог хранения файлов инициализирован: {}", this.storageDirectory);
        } catch (IOException e) {
            throw new RuntimeException("Не удалось создать каталог для хранения файлов: " + this.storageDirectory, e);
        }
    }

    /**
     * Сохраняет файл на диск с уникальным именем на основе UUID.
     *
     * @param file загруженный файл
     * @return метаданные о сохранённом файле: [уникальное имя, относительный путь]
     */
    public StoredFileMetadata store(MultipartFile file) {
        String originalFilename = file.getOriginalFilename();
        String extension = FileValidator.getFileExtension(originalFilename);

        // Генерируем уникальное имя файла, исключающее коллизии имён
        String storedFilename = UUID.randomUUID().toString() + (extension.isEmpty() ? "" : "." + extension);
        Path targetLocation = this.storageDirectory.resolve(storedFilename).normalize();

        // Проверка: файл гарантированно должен лежать внутри storageDirectory
        if (!targetLocation.startsWith(this.storageDirectory)) {
            throw new FileValidationException("Недопустимый путь сохранения файла.");
        }

        try {
            Files.copy(file.getInputStream(), targetLocation, StandardCopyOption.REPLACE_EXISTING);
            logger.info("Файл успешно сохранён на диск: {} (исходное: {})", storedFilename, originalFilename);
            return new StoredFileMetadata(storedFilename, targetLocation.toString());
        } catch (IOException e) {
            logger.error("Ошибка записи файла на диск: {}", originalFilename, e);
            throw new RuntimeException("Не удалось сохранить файл: " + originalFilename, e);
        }
    }

    /**
     * Загружает файл в виде Spring Resource для отображения или скачивания.
     */
    public Resource loadAsResource(String storedFilename) {
        try {
            Path filePath = this.storageDirectory.resolve(storedFilename).normalize();
            Resource resource = new UrlResource(filePath.toUri());
            if (resource.exists() && resource.isReadable()) {
                return resource;
            } else {
                throw new FileValidationException("Файл не найден на диске: " + storedFilename);
            }
        } catch (MalformedURLException e) {
            throw new FileValidationException("Некорректный путь к файлу: " + storedFilename);
        }
    }

    /**
     * Удаляет файл с диска.
     */
    public boolean delete(String storedFilename) {
        try {
            Path filePath = this.storageDirectory.resolve(storedFilename).normalize();
            boolean deleted = Files.deleteIfExists(filePath);
            if (deleted) {
                logger.info("Файл удалён с диска: {}", storedFilename);
            }
            return deleted;
        } catch (IOException e) {
            logger.warn("Не удалось удалить файл с диска: {}", storedFilename, e);
            return false;
        }
    }

    public Path getStorageDirectory() {
        return storageDirectory;
    }

    public record StoredFileMetadata(String storedFilename, String fullPath) {}
}

