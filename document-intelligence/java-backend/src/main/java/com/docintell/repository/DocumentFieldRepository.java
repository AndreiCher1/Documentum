package com.docintell.repository;

import com.docintell.entity.DocumentField;
import com.docintell.enums.FieldType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * Репозиторий извлечённых полей документов: DocumentFieldRepository
 *
 * Позволяет выполнять поиск по структурированным полям документов.
 * Например: найти все документы, где ИНН равен "7701234567"
 * или сумма превышает 100 000 руб.
 */
@Repository
public interface DocumentFieldRepository extends JpaRepository<DocumentField, Long> {

    /**
     * Получить все поля конкретного документа.
     */
    List<DocumentField> findByDocumentId(Long documentId);

    /**
     * Поиск по имени поля и значению (например: fieldName = "inn", fieldValue = "7701234567").
     */
    List<DocumentField> findByFieldNameAndFieldValueContainingIgnoreCase(String fieldName, String value);

    /**
     * Поиск по семантическому типу поля (например, все поля с типом AMOUNT).
     */
    List<DocumentField> findByFieldType(FieldType fieldType);

    /**
     * Поиск полей с низкой уверенностью для конкретного документа (для отображения бейджа ⚠️).
     */
    List<DocumentField> findByDocumentIdAndConfidenceLessThan(Long documentId, Double minConfidence);

    /**
     * Удалить все поля конкретного документа (при перезапуске анализа).
     */
    void deleteByDocumentId(Long documentId);

    /**
     * Полнотекстовый поиск по содержимому любых полей.
     */
    @Query("SELECT f FROM DocumentField f WHERE LOWER(f.fieldValue) LIKE LOWER(CONCAT('%', :query, '%'))")
    List<DocumentField> searchByValue(@Param("query") String query);
}

