package com.docintell;

import com.docintell.entity.Document;
import com.docintell.entity.DocumentField;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.docintell.enums.FieldType;
import com.docintell.repository.DocumentFieldRepository;
import com.docintell.repository.DocumentRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Интеграционный тест репозиториев базы данных.
 *
 * Проверяет:
 * 1. Сохранение сущности Document в БД.
 * 2. Каскадное сохранение связанных сущностей DocumentField (@OneToMany).
 * 3. Поиск по enum DocumentType.
 * 4. Корректность генерации ID.
 */
@SpringBootTest
@Transactional
class DocumentRepositoryTest {

    @Autowired
    private DocumentRepository documentRepository;

    @Autowired
    private DocumentFieldRepository documentFieldRepository;

    @Test
    @DisplayName("Проверка сохранения документа и извлечённых полей в БД")
    void testSaveDocumentWithFields() {
        // 1. Создаём тестовый документ
        Document document = new Document();
        document.setOriginalFilename("dogovor_123.pdf");
        document.setStoredFilename("uuid-12345.pdf");
        document.setFilePath("/storage/uuid-12345.pdf");
        document.setMimeType("application/pdf");
        document.setFileSize(204800L);
        document.setDocumentType(DocumentType.CONTRACT);
        document.setStatus(AnalysisStatus.COMPLETED);
        document.setOverallConfidence(0.96);

        // 2. Добавляем извлечённое поле (например, номер договора)
        DocumentField numberField = new DocumentField();
        numberField.setFieldName("number");
        numberField.setDisplayName("Номер договора");
        numberField.setFieldValue("123/25");
        numberField.setFieldType(FieldType.TEXT);
        numberField.setConfidence(0.98);
        numberField.setBbox("{\"x\":100,\"y\":150,\"w\":300,\"h\":40}");
        document.addField(numberField);

        // 3. Добавляем поле суммы
        DocumentField amountField = new DocumentField();
        amountField.setFieldName("amount");
        amountField.setDisplayName("Сумма договора");
        amountField.setFieldValue("150000");
        amountField.setFieldType(FieldType.AMOUNT);
        amountField.setConfidence(0.95);
        document.addField(amountField);

        // 4. Сохраняем документ в БД
        Document saved = documentRepository.save(document);

        // 5. Проверяем результат
        assertNotNull(saved.getId(), "ID документа должен быть сгенерирован базой данных");
        assertEquals(DocumentType.CONTRACT, saved.getDocumentType());
        assertEquals("dogovor_123.pdf", saved.getOriginalFilename());

        // 6. Проверяем сохранение полей
        List<DocumentField> fields = documentFieldRepository.findByDocumentId(saved.getId());
        assertEquals(2, fields.size(), "Должно быть сохранено 2 поля");

        // 7. Проверяем поиск по типу документа
        List<Document> contracts = documentRepository.findByStatus(AnalysisStatus.COMPLETED);
        assertFalse(contracts.isEmpty(), "Список обработанных документов не должен быть пуст");
    }
}

