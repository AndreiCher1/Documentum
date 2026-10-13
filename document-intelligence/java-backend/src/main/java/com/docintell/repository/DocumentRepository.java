package com.docintell.repository;

import com.docintell.entity.Document;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Репозиторий документов: DocumentRepository
 *
 * ЧТО ТАКОЕ REPOSITORY?
 * Репозиторий — это слой доступа к базе данных.
 *
 * КАК ЭТО РАБОТАЕТ В SPRING DATA JPA?
 * Мы объявляем интерфейс, наследующий JpaRepository<Document, Long>.
 * Spring Data автоматически создаёт готовую реализацию со всеми базовыми методами:
 * - save(document) — сохранить или обновить запись (INSERT / UPDATE)
 * - findById(id) — найти по первичному ключу (SELECT WHERE id = ?)
 * - findAll() — получить все записи (SELECT * FROM documents)
 * - deleteById(id) — удалить по первичному ключу (DELETE WHERE id = ?)
 * - count() — подсчитать общее число записей
 *
 * МЕТОДЫ ПО ИМЕНИ (Query Creation):
 * Spring сам разбирает название метода:
 * findByDocumentType(type) -> WHERE document_type = ?
 * findByStatus(status) -> WHERE status = ?
 *
 * Никаких ручных SQL-запросов писать не требуется!
 */
@Repository
public interface DocumentRepository extends JpaRepository<Document, Long> {

    /**
     * Поиск документов по типу с пагинацией.
     */
    Page<Document> findByDocumentType(DocumentType documentType, Pageable pageable);

    /**
     * Поиск документов по статусу обработки.
     */
    List<Document> findByStatus(AnalysisStatus status);

    /**
     * Поиск документов с низкой уверенностью (требующих ручной проверки пользователем).
     */
    List<Document> findByOverallConfidenceLessThanEqual(Double maxConfidence);

    /**
     * Поиск по оригинальному имени файла (без учёта регистра).
     */
    List<Document> findByOriginalFilenameContainingIgnoreCase(String filename);

    /**
     * Подсчёт количества документов по типу (для страницы Dashboard).
     */
    long countByDocumentType(DocumentType documentType);

    /**
     * Подсчёт количества документов по статусу.
     */
    long countByStatus(AnalysisStatus status);

    /**
     * Получение средневзвешенного confidence по всем обработанным документам.
     */
    @Query("SELECT AVG(d.overallConfidence) FROM Document d WHERE d.status = :status")
    Double calculateAverageConfidenceByStatus(@Param("status") AnalysisStatus status);

    /**
     * Поиск документов за период дат.
     */
    List<Document> findByCreatedAtBetween(LocalDateTime start, LocalDateTime end);

    /**
     * Суммарный объем всех файлов в хранилище (в байтах).
     */
    @Query("SELECT COALESCE(SUM(d.fileSize), 0) FROM Document d")
    Long calculateTotalFileSize();

    /**
     * Группировка и подсчет документов по категориям.
     */
    @Query("SELECT d.documentType, COUNT(d) FROM Document d GROUP BY d.documentType")
    List<Object[]> countGroupedByDocumentType();
}

