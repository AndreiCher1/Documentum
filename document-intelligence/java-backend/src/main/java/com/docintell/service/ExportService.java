package com.docintell.service;

import com.docintell.dto.DocumentResponse;
import com.docintell.entity.Document;
import com.docintell.entity.DocumentField;
import com.docintell.repository.DocumentFieldRepository;
import com.docintell.repository.DocumentRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * Сервис универсального экспорта данных в CSV (Excel-совместимый UTF-8 с BOM) и JSON (Этап 11).
 */
@Service
public class ExportService {

    private static final Logger logger = LoggerFactory.getLogger(ExportService.class);
    private static final DateTimeFormatter DATE_FMT = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final DocumentRepository documentRepository;
    private final DocumentFieldRepository documentFieldRepository;
    private final DocumentService documentService;
    private final ObjectMapper objectMapper;

    public ExportService(
            DocumentRepository documentRepository,
            DocumentFieldRepository documentFieldRepository,
            DocumentService documentService,
            ObjectMapper objectMapper
    ) {
        this.documentRepository = documentRepository;
        this.documentFieldRepository = documentFieldRepository;
        this.documentService = documentService;
        this.objectMapper = objectMapper;
    }

    /**
     * Экспорт всего реестра документов в CSV с поддержкой русской локали Excel (UTF-8 BOM, разделитель ';').
     */
    @Transactional(readOnly = true)
    public byte[] exportAllDocumentsCsv() {
        List<Document> docs = documentRepository.findAll();
        StringBuilder sb = new StringBuilder();

        // UTF-8 BOM для автоматического распознавания кириллицы в Microsoft Excel
        sb.append('\uFEFF');

        // Заголовки таблицы
        sb.append("ID;Имя файла;Тип документа;Категория;Статус;Уверенность (%);Размер (байт);Дата загрузки\r\n");

        for (Document d : docs) {
            String confPct = d.getOverallConfidence() != null
                    ? String.format(Locale.ROOT, "%.1f", d.getOverallConfidence() * 100.0)
                    : "0.0";
            String dateStr = d.getCreatedAt() != null ? d.getCreatedAt().format(DATE_FMT) : "";

            sb.append(d.getId()).append(';')
                    .append(escapeCsv(d.getOriginalFilename())).append(';')
                    .append(d.getDocumentType() != null ? d.getDocumentType().name() : "").append(';')
                    .append(escapeCsv(d.getDocumentType() != null ? d.getDocumentType().getDisplayName() : "")).append(';')
                    .append(d.getStatus() != null ? d.getStatus().name() : "").append(';')
                    .append(confPct).append(';')
                    .append(d.getFileSize() != null ? d.getFileSize() : 0).append(';')
                    .append(dateStr).append("\r\n");
        }

        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Экспорт всей базы документов с извлеченными полями в структурированный JSON.
     */
    @Transactional(readOnly = true)
    public byte[] exportAllDocumentsJson() {
        try {
            List<Document> docs = documentRepository.findAll();
            List<Map<String, Object>> resultList = new ArrayList<>();

            for (Document d : docs) {
                DocumentResponse docResp = documentService.getDocumentById(d.getId());
                Map<String, Object> map = new LinkedHashMap<>();
                map.put("id", docResp.id());
                map.put("originalFilename", docResp.originalFilename());
                map.put("documentType", docResp.documentType());
                map.put("documentTypeDisplayName", docResp.documentTypeDisplayName());
                map.put("status", docResp.status());
                map.put("overallConfidence", docResp.overallConfidence());
                map.put("fileSize", docResp.fileSize());
                map.put("createdAt", docResp.createdAt() != null ? docResp.createdAt().toString() : null);
                map.put("fields", docResp.fields());
                resultList.add(map);
            }

            String json = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(resultList);
            return json.getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            logger.error("Ошибка экспорта в JSON: {}", e.getMessage(), e);
            throw new RuntimeException("Ошибка экспорта в JSON: " + e.getMessage(), e);
        }
    }

    /**
     * Экспорт извлеченных реквизитов конкретного документа в CSV.
     */
    @Transactional(readOnly = true)
    public byte[] exportDocumentFieldsCsv(Long documentId) {
        DocumentResponse doc = documentService.getDocumentById(documentId);
        List<DocumentField> fields = documentFieldRepository.findByDocumentId(documentId);

        StringBuilder sb = new StringBuilder();
        sb.append('\uFEFF');
        sb.append("Документ: ").append(doc.originalFilename()).append(" (ID: #").append(doc.id()).append(")\r\n");
        sb.append("Тип: ").append(doc.documentTypeDisplayName()).append("; Статус: ").append(doc.status()).append("\r\n\r\n");
        sb.append("Код поля;Название реквизита;Значение;Тип;Уверенность (%);Проверено\r\n");

        for (DocumentField f : fields) {
            String conf = f.getConfidence() != null
                    ? String.format(Locale.ROOT, "%.1f", f.getConfidence() * 100.0)
                    : "0.0";

            sb.append(escapeCsv(f.getFieldName())).append(';')
                    .append(escapeCsv(f.getDisplayName())).append(';')
                    .append(escapeCsv(f.getFieldValue())).append(';')
                    .append(f.getFieldType() != null ? f.getFieldType().name() : "").append(';')
                    .append(conf).append(';')
                    .append(Boolean.TRUE.equals(f.getValidated()) ? "Да" : "Нет")
                    .append("\r\n");
        }

        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    /**
     * Экспорт конкретного документа в JSON.
     */
    @Transactional(readOnly = true)
    public byte[] exportDocumentJson(Long documentId) {
        try {
            DocumentResponse doc = documentService.getDocumentById(documentId);
            String json = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(doc);
            return json.getBytes(StandardCharsets.UTF_8);
        } catch (Exception e) {
            logger.error("Ошибка экспорта документа #{} в JSON: {}", documentId, e.getMessage(), e);
            throw new RuntimeException("Ошибка экспорта документа в JSON: " + e.getMessage(), e);
        }
    }

    private String escapeCsv(String value) {
        if (value == null) return "";
        String clean = value.replace("\r", " ").replace("\n", " ");
        if (clean.contains(";") || clean.contains("\"") || clean.contains(",")) {
            return "\"" + clean.replace("\"", "\"\"") + "\"";
        }
        return clean;
    }
}
