package com.docintell.service;

import com.docintell.dto.DocumentListItemResponse;
import com.docintell.dto.DocumentResponse;
import com.docintell.dto.DocumentUploadResponse;
import com.docintell.entity.Document;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.docintell.exception.DocumentNotFoundException;
import com.docintell.mapper.DocumentMapper;
import com.docintell.repository.DocumentRepository;
import com.docintell.validation.FileValidator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.Resource;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/**
 * Сервис управления документами: DocumentService
 *
 * СЛОЙ БИЗНЕС-ЛОГИКИ:
 * Содержит все сценарии работы с документами приложения:
 * - Валидация входных файлов
 * - Сохранение в хранилище и в базу данных
 * - Поиск и постраничная выдача
 * - Безопасное удаление документа и связанного файла
 */
@Service
public class DocumentService {

    private static final Logger logger = LoggerFactory.getLogger(DocumentService.class);

    private final DocumentRepository documentRepository;
    private final FileStorageService fileStorageService;
    private final FileValidator fileValidator;
    private final DocumentMapper documentMapper;
    private final AiServiceClient aiServiceClient;
    private final com.docintell.repository.AnalysisResultRepository analysisResultRepository;
    private final com.docintell.repository.DocumentFieldRepository documentFieldRepository;
    private final com.fasterxml.jackson.databind.ObjectMapper objectMapper;

    public DocumentService(
            DocumentRepository documentRepository,
            FileStorageService fileStorageService,
            FileValidator fileValidator,
            DocumentMapper documentMapper,
            AiServiceClient aiServiceClient,
            com.docintell.repository.AnalysisResultRepository analysisResultRepository,
            com.docintell.repository.DocumentFieldRepository documentFieldRepository,
            com.fasterxml.jackson.databind.ObjectMapper objectMapper
    ) {
        this.documentRepository = documentRepository;
        this.fileStorageService = fileStorageService;
        this.fileValidator = fileValidator;
        this.documentMapper = documentMapper;
        this.aiServiceClient = aiServiceClient;
        this.analysisResultRepository = analysisResultRepository;
        this.documentFieldRepository = documentFieldRepository;
        this.objectMapper = objectMapper;
    }


    /**
     * Сценарий: Загрузка нового документа в систему.
     */
    @Transactional
    public DocumentUploadResponse uploadDocument(MultipartFile file) {
        logger.info("Начало обработки загрузки файла: {}", file.getOriginalFilename());

        // 1. Проверяем файл на безопасность, размер и расширение
        fileValidator.validate(file);

        // 2. Сохраняем физический файл на диск в каталог uploads
        FileStorageService.StoredFileMetadata metadata = fileStorageService.store(file);

        // 3. Создаём сущность Document для базы данных
        Document document = new Document();
        document.setOriginalFilename(file.getOriginalFilename());
        document.setStoredFilename(metadata.storedFilename());
        document.setFilePath(metadata.fullPath());
        document.setFileSize(file.getSize());
        document.setMimeType(file.getContentType() != null ? file.getContentType() : "application/octet-stream");
        document.setDocumentType(DocumentType.UNKNOWN);
        document.setStatus(AnalysisStatus.UPLOADED);
        document.setOverallConfidence(0.0);

        // 4. Сохраняем в PostgreSQL / H2
        Document saved = documentRepository.save(document);
        logger.info("Документ успешно зарегистрирован в БД с ID: {}", saved.getId());

        // 5. Преобразуем в DTO для ответа клиенту
        return documentMapper.toUploadResponse(saved);
    }

    /**
     * Получение страницы со списком документов (с пагинацией и сортировкой).
     */
    @Transactional(readOnly = true)
    public Page<DocumentListItemResponse> getAllDocuments(Pageable pageable) {
        return documentRepository.findAll(pageable)
                .map(documentMapper::toListItemResponse);
    }

    /**
     * Получение последних загруженных документов (для Dashboard).
     */
    @Transactional(readOnly = true)
    public List<DocumentListItemResponse> getRecentDocuments(int limit) {
        Pageable pageable = org.springframework.data.domain.PageRequest.of(
                0,
                limit,
                org.springframework.data.domain.Sort.by(
                        org.springframework.data.domain.Sort.Direction.DESC,
                        "createdAt"
                )
        );
        return documentRepository.findAll(pageable)
                .map(documentMapper::toListItemResponse)
                .getContent();
    }

    /**
     * Получение полной информации о документе по ID.
     */
    @Transactional(readOnly = true)
    public DocumentResponse getDocumentById(Long id) {
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException(id));
        return documentMapper.toDocumentResponse(document);
    }

    /**
     * Получение бинарного файла для скачивания или превью в Electron.
     */
    @Transactional(readOnly = true)
    public Resource getDocumentFile(Long id) {
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException(id));
        return fileStorageService.loadAsResource(document.getStoredFilename());
    }

    /**
     * Получение визуального превью страницы (для PDF конвертируется в PNG через AI-сервис).
     */
    @Transactional(readOnly = true)
    public Resource getDocumentPreview(Long id, int page) {
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException(id));

        String storedFilename = document.getStoredFilename();
        if (document.getMimeType() != null && document.getMimeType().contains("pdf")) {
            String previewFilename = storedFilename + "_p" + page + ".png";
            java.nio.file.Path previewPath = fileStorageService.getStorageDirectory().resolve(previewFilename);
            if (java.nio.file.Files.exists(previewPath)) {
                return fileStorageService.loadAsResource(previewFilename);
            }
            try {
                Resource originalResource = fileStorageService.loadAsResource(storedFilename);
                byte[] bytes = originalResource.getContentAsByteArray();
                byte[] pngBytes = aiServiceClient.renderPage(bytes, document.getOriginalFilename(), page);
                if (pngBytes != null && pngBytes.length > 0) {
                    java.nio.file.Files.write(previewPath, pngBytes);
                    return fileStorageService.loadAsResource(previewFilename);
                }
            } catch (Exception e) {
                logger.warn("Не удалось сгенерировать PNG превью страницы {} для PDF: {}", page, e.getMessage());
            }
        }
        return fileStorageService.loadAsResource(storedFilename);
    }

    /**
     * Удаление документа из системы: удаляет запись из БД и физический файл с диска.
     */
    @Transactional
    public void deleteDocument(Long id) {
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException(id));

        String storedFilename = document.getStoredFilename();
        documentRepository.delete(document);
        fileStorageService.delete(storedFilename);

        logger.info("Документ с ID {} и его файл {} успешно удалены", id, storedFilename);
    }

    /**
     * Подсчёт общего количества документов.
     */
    @Transactional(readOnly = true)
    public long countTotalDocuments() {
        return documentRepository.count();
    }

    /**
     * Сценарий: Запуск AI-анализа документа (предобработка + распознавание текста OCR).
     *
     * 1. Переводит статус документа в PROCESSING.
     * 2. Читает файл из хранилища и отправляет в Python AI Service.
     * 3. Сохраняет структурированный результат в analysis_results и обновляет Document.
     *
     * @param id идентификатор документа
     * @return результат анализа с распознанными блоками текста и метриками качества
     */
    @Transactional
    public com.docintell.dto.AnalysisResultResponse analyzeDocument(Long id) {
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException(id));

        logger.info("Старт анализа документа ID {}: '{}'", id, document.getOriginalFilename());
        document.setStatus(AnalysisStatus.PROCESSING);
        documentRepository.save(document);

        try {
            Resource resource = fileStorageService.loadAsResource(document.getStoredFilename());
            byte[] bytes = resource.getContentAsByteArray();

            com.docintell.dto.ai.AiAnalyzeResponse aiResponse =
                    aiServiceClient.analyzeDocument(bytes, document.getOriginalFilename());

            com.docintell.entity.AnalysisResult result = new com.docintell.entity.AnalysisResult();
            result.setDocument(document);
            result.setAnalyzerName("PaddleOCR_PP-OCRv5");
            result.setStatus(aiResponse.status());
            result.setProcessingTimeMs(aiResponse.processingTimeMs() != null ? aiResponse.processingTimeMs() : 0.0);

            String detectedTypeStr = aiResponse.documentType() != null ? aiResponse.documentType().type() : "UNKNOWN";
            Double typeConf = aiResponse.documentType() != null ? aiResponse.documentType().confidence() : 0.0;
            result.setDetectedType(detectedTypeStr);
            result.setTypeConfidence(typeConf);

            result.setRawResult(objectMapper.writeValueAsString(aiResponse));
            result.setOcrResult(objectMapper.writeValueAsString(aiResponse.ocrResults()));

            // Обновляем классифицированный тип документа (Этап 6)
            com.docintell.enums.DocumentType detectedDocType = com.docintell.enums.DocumentType.fromString(detectedTypeStr);
            document.setDocumentType(detectedDocType);

            document.setStatus(AnalysisStatus.COMPLETED);
            document.setOverallConfidence(aiResponse.overallConfidence() != null ? aiResponse.overallConfidence() : 0.0);
            document.addAnalysisResult(result);

            // Очищаем старые поля и сохраняем новые извлечённые структурированные поля (Этап 7)
            if (document.getFields() != null) {
                document.getFields().clear();
            }
            documentFieldRepository.deleteByDocumentId(document.getId());

            if (aiResponse.fields() != null) {
                for (var fDto : aiResponse.fields()) {
                    com.docintell.entity.DocumentField field = new com.docintell.entity.DocumentField();
                    field.setDocument(document);
                    field.setFieldName(fDto.name());
                    field.setDisplayName(fDto.displayName());
                    field.setFieldValue(fDto.value());
                    field.setFieldType(com.docintell.enums.FieldType.fromString(fDto.fieldType()));
                    field.setConfidence(fDto.confidence() != null ? fDto.confidence() : 0.0);
                    if (fDto.bbox() != null && !fDto.bbox().isEmpty()) {
                        try {
                            field.setBbox(objectMapper.writeValueAsString(fDto.bbox()));
                        } catch (Exception ignored) {}
                    }
                    field.setPageNumber(fDto.page() != null ? fDto.page() : 1);
                    boolean isValidated = false;
                    if (aiResponse.validation() != null && aiResponse.validation().rules() != null) {
                        for (var rule : aiResponse.validation().rules()) {
                            if (fDto.name().equalsIgnoreCase(rule.fieldName()) && "PASS".equalsIgnoreCase(rule.status())) {
                                isValidated = true;
                                break;
                            }
                        }
                    }
                    field.setValidated(isValidated);
                    document.addField(field);
                }
            }

            com.docintell.entity.AnalysisResult savedResult = analysisResultRepository.save(result);
            Document savedDocument = documentRepository.save(document);

            logger.info("Анализ документа ID {} успешно завершён. Тип: {}, полей: {}, Статус: COMPLETED",
                    id, detectedDocType.getDisplayName(), savedDocument.getFields().size());
            return toAnalysisResultResponse(savedResult, aiResponse, savedDocument);


        } catch (Exception e) {
            logger.error("Ошибка при анализе документа ID {}: {}", id, e.getMessage(), e);
            document.setStatus(AnalysisStatus.FAILED);
            documentRepository.save(document);

            com.docintell.entity.AnalysisResult failedResult = new com.docintell.entity.AnalysisResult();
            failedResult.setDocument(document);
            failedResult.setAnalyzerName("PaddleOCR_PP-OCRv5");
            failedResult.setStatus("failed");
            failedResult.setErrorMessage(e.getMessage());
            analysisResultRepository.save(failedResult);

            throw new RuntimeException("Ошибка выполнения анализа документа: " + e.getMessage(), e);
        }
    }

    /**
     * Получение последнего результата анализа документа по ID.
     */
    @Transactional(readOnly = true)
    public java.util.Optional<com.docintell.dto.AnalysisResultResponse> getLatestAnalysis(Long id) {
        Document document = documentRepository.findById(id)
                .orElseThrow(() -> new DocumentNotFoundException(id));

        return analysisResultRepository.findFirstByDocumentIdOrderByCreatedAtDesc(id)
                .map(result -> {
                    com.docintell.dto.ai.AiAnalyzeResponse aiResponse = null;
                    if (result.getRawResult() != null) {
                        try {
                            aiResponse = objectMapper.readValue(result.getRawResult(), com.docintell.dto.ai.AiAnalyzeResponse.class);
                        } catch (Exception e) {
                            logger.warn("Не удалось десериализовать rawResult для анализа ID {}: {}", result.getId(), e.getMessage());
                        }
                    }
                    return toAnalysisResultResponse(result, aiResponse, document);
                });
    }

    private com.docintell.dto.AnalysisResultResponse toAnalysisResultResponse(
            com.docintell.entity.AnalysisResult result,
            com.docintell.dto.ai.AiAnalyzeResponse aiResponse,
            Document document
    ) {
        List<com.docintell.dto.ai.AiAnalyzeResponse.OcrResultDto> ocrBlocks = java.util.Collections.emptyList();
        com.docintell.dto.ai.AiAnalyzeResponse.QualityMetricsDto quality = null;
        Integer totalPages = 1;

        com.docintell.dto.ai.AiAnalyzeResponse.ValidationSummaryDto validation = null;
        if (aiResponse != null) {
            validation = aiResponse.validation();
            if (aiResponse.ocrResults() != null) {
                ocrBlocks = aiResponse.ocrResults();
            }
            quality = aiResponse.quality();
            if (aiResponse.totalPages() != null) {
                totalPages = aiResponse.totalPages();
            }
        }

        List<com.docintell.dto.DocumentFieldResponse> fieldResponses = java.util.Collections.emptyList();
        if (document.getFields() != null) {
            fieldResponses = document.getFields().stream()
                    .map(documentMapper::toFieldResponse)
                    .toList();
        }

        String typeDisplayName = "Не определен";
        String explanation = null;
        if (aiResponse != null && aiResponse.documentType() != null) {
            if (aiResponse.documentType().displayName() != null) {
                typeDisplayName = aiResponse.documentType().displayName();
            } else {
                typeDisplayName = com.docintell.enums.DocumentType.fromString(result.getDetectedType()).getDisplayName();
            }
            explanation = aiResponse.documentType().explanation();
        } else if (result.getDetectedType() != null) {
            typeDisplayName = com.docintell.enums.DocumentType.fromString(result.getDetectedType()).getDisplayName();
        }

        return new com.docintell.dto.AnalysisResultResponse(
                result.getId(),
                document.getId(),
                result.getStatus(),
                result.getProcessingTimeMs(),
                result.getDetectedType(),
                typeDisplayName,
                result.getTypeConfidence(),
                explanation,
                document.getOverallConfidence(),
                totalPages,
                quality,
                ocrBlocks,
                fieldResponses,
                validation,
                result.getCreatedAt(),
                result.getErrorMessage()
        );
    }
}


