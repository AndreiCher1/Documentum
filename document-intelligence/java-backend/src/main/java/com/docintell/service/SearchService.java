package com.docintell.service;

import com.docintell.dto.SearchRequest;
import com.docintell.dto.SearchResponse;
import com.docintell.dto.SearchResponse.MatchedFieldDto;
import com.docintell.dto.SearchResponse.SearchResultItem;
import com.docintell.entity.AnalysisResult;
import com.docintell.entity.Document;
import com.docintell.entity.DocumentField;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.docintell.repository.AnalysisResultRepository;
import com.docintell.repository.DocumentFieldRepository;
import com.docintell.repository.DocumentRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

/**
 * Сервис полнотекстового и параметрического поиска документов (Этап 10).
 *
 * Позволяет находить документы по:
 * - Текстовому запросу (имя файла, распознанные поля, OCR-текст)
 * - Категории / типу документа (Паспорт РФ, СНИЛС, Водительское удостоверение, Квитанция ЖКУ и т.д.)
 * - Диапазону дат создания
 * - Минимальному уровню уверенности AI (confidence)
 * - Статусу обработки
 */
@Service
public class SearchService {

    private static final Logger logger = LoggerFactory.getLogger(SearchService.class);

    private final DocumentRepository documentRepository;
    private final DocumentFieldRepository documentFieldRepository;
    private final AnalysisResultRepository analysisResultRepository;
    private final ObjectMapper objectMapper;

    public SearchService(
            DocumentRepository documentRepository,
            DocumentFieldRepository documentFieldRepository,
            AnalysisResultRepository analysisResultRepository,
            ObjectMapper objectMapper
    ) {
        this.documentRepository = documentRepository;
        this.documentFieldRepository = documentFieldRepository;
        this.analysisResultRepository = analysisResultRepository;
        this.objectMapper = objectMapper;
    }

    /**
     * Выполнить поиск документов по параметрам запроса.
     */
    @Transactional(readOnly = true)
    public SearchResponse search(SearchRequest request) {
        logger.info("Поиск документов: query='{}', type='{}', status='{}', conf={}",
                request.query(), request.documentType(), request.status(), request.minConfidence());

        // 1. Получаем все документы из базы данных
        List<Document> allDocs = documentRepository.findAll();

        // 2. Параметрическая фильтрация
        List<Document> filtered = allDocs.stream()
                .filter(doc -> matchesParametricFilters(doc, request))
                .collect(Collectors.toList());

        final String q = (request.query() != null) ? request.query().trim() : "";
        final boolean hasQuery = !q.isEmpty();

        List<MatchHolder> matchedHolders = new ArrayList<>();

        for (Document doc : filtered) {
            List<DocumentField> fields = documentFieldRepository.findByDocumentId(doc.getId());
            List<AnalysisResult> analyses = analysisResultRepository.findByDocumentIdOrderByCreatedAtDesc(doc.getId());

            if (!hasQuery) {
                // Если поисковый запрос пустой — включаем все документы, удовлетворяющие параметрам
                List<MatchedFieldDto> previewFields = fields.stream()
                        .limit(4)
                        .map(f -> new MatchedFieldDto(f.getFieldName(), f.getDisplayName(), f.getFieldValue(), f.getConfidence()))
                        .collect(Collectors.toList());

                matchedHolders.add(new MatchHolder(doc, previewFields, Collections.emptyList(), 0));
            } else {
                // Полнотекстовый поиск: проверяем имя файла, поля и сырой OCR-текст
                int relevanceScore = 0;
                List<MatchedFieldDto> matchedFields = new ArrayList<>();
                List<String> snippets = new ArrayList<>();

                String filename = doc.getOriginalFilename() != null ? doc.getOriginalFilename() : "";
                if (containsIgnoreCase(filename, q)) {
                    relevanceScore += 10;
                    snippets.add("Имя файла: " + highlight(filename, q));
                }

                for (DocumentField f : fields) {
                    boolean valMatch = f.getFieldValue() != null && containsIgnoreCase(f.getFieldValue(), q);
                    boolean nameMatch = f.getDisplayName() != null && containsIgnoreCase(f.getDisplayName(), q);

                    if (valMatch || nameMatch) {
                        relevanceScore += 5;
                        matchedFields.add(new MatchedFieldDto(
                                f.getFieldName(),
                                f.getDisplayName(),
                                f.getFieldValue(),
                                f.getConfidence()
                        ));
                        if (valMatch) {
                            snippets.add(f.getDisplayName() + ": " + highlight(f.getFieldValue(), q));
                        }
                    }
                }

                // Проверяем распознанный текст OCR
                for (AnalysisResult ar : analyses) {
                    List<String> ocrTexts = extractOcrTexts(ar);
                    for (String line : ocrTexts) {
                        if (containsIgnoreCase(line, q)) {
                            relevanceScore += 2;
                            snippets.add("Текст документа: " + highlight(line, q));
                            if (snippets.size() >= 5) break;
                        }
                    }
                    if (snippets.size() >= 5) break;
                }

                if (relevanceScore > 0) {
                    // Ограничиваем количество сниппетов до 5 для компактности
                    List<String> limitedSnippets = snippets.stream().limit(5).collect(Collectors.toList());
                    matchedHolders.add(new MatchHolder(doc, matchedFields, limitedSnippets, relevanceScore));
                }
            }
        }

        // 3. Сортировка: сначала по релевантности (если был текстовый запрос), затем по дате создания (новые первыми)
        if (hasQuery) {
            matchedHolders.sort((a, b) -> {
                int cmp = Integer.compare(b.relevanceScore, a.relevanceScore);
                if (cmp != 0) return cmp;
                return b.doc.getCreatedAt().compareTo(a.doc.getCreatedAt());
            });
        } else {
            matchedHolders.sort((a, b) -> b.doc.getCreatedAt().compareTo(a.doc.getCreatedAt()));
        }

        // 4. Пагинация
        int totalElements = matchedHolders.size();
        int pageSize = request.size() != null && request.size() > 0 ? request.size() : 20;
        int currentPage = request.page() != null && request.page() >= 0 ? request.page() : 0;
        int totalPages = (int) Math.ceil((double) totalElements / pageSize);

        int fromIndex = Math.min(currentPage * pageSize, totalElements);
        int toIndex = Math.min(fromIndex + pageSize, totalElements);

        List<MatchHolder> pageHolders = matchedHolders.subList(fromIndex, toIndex);

        List<SearchResultItem> items = pageHolders.stream()
                .map(holder -> new SearchResultItem(
                        holder.doc.getId(),
                        holder.doc.getOriginalFilename(),
                        holder.doc.getDocumentType() != null ? holder.doc.getDocumentType().name() : "UNKNOWN",
                        holder.doc.getDocumentType() != null ? holder.doc.getDocumentType().getDisplayName() : "Не определён",
                        holder.doc.getStatus() != null ? holder.doc.getStatus().name() : "UPLOADED",
                        holder.doc.getOverallConfidence(),
                        holder.doc.getFileSize(),
                        holder.doc.getCreatedAt(),
                        holder.matchedFields,
                        holder.snippets
                ))
                .collect(Collectors.toList());

        return new SearchResponse(totalElements, totalPages, currentPage, pageSize, items);
    }

    private boolean matchesParametricFilters(Document doc, SearchRequest req) {
        // Фильтр по типу документа
        if (req.documentType() != null && !req.documentType().isBlank() && !"ALL".equalsIgnoreCase(req.documentType())) {
            try {
                DocumentType reqType = DocumentType.valueOf(req.documentType().toUpperCase());
                if (doc.getDocumentType() != reqType) {
                    return false;
                }
            } catch (IllegalArgumentException ignored) {
                // Если передан неизвестный тип документа
            }
        }

        // Фильтр по статусу
        if (req.status() != null && !req.status().isBlank() && !"ALL".equalsIgnoreCase(req.status())) {
            try {
                AnalysisStatus reqStatus = AnalysisStatus.valueOf(req.status().toUpperCase());
                if (doc.getStatus() != reqStatus) {
                    return false;
                }
            } catch (IllegalArgumentException ignored) {
                // Если передан неизвестный статус
            }
        }

        // Фильтр по минимальной уверенности
        if (req.minConfidence() != null && req.minConfidence() > 0) {
            double threshold = req.minConfidence();
            if (threshold > 1.0) {
                threshold = threshold / 100.0; // нормализуем 0-100 в 0.0-1.0
            }
            double docConf = doc.getOverallConfidence() != null ? doc.getOverallConfidence() : 0.0;
            if (docConf < threshold) {
                return false;
            }
        }

        // Фильтр по дате "с"
        if (req.dateFrom() != null) {
            LocalDateTime start = req.dateFrom().atStartOfDay();
            if (doc.getCreatedAt() != null && doc.getCreatedAt().isBefore(start)) {
                return false;
            }
        }

        // Фильтр по дате "по"
        if (req.dateTo() != null) {
            LocalDateTime end = req.dateTo().atTime(LocalTime.MAX);
            if (doc.getCreatedAt() != null && doc.getCreatedAt().isAfter(end)) {
                return false;
            }
        }

        return true;
    }

    private boolean containsIgnoreCase(String source, String query) {
        if (source == null || query == null) return false;
        return source.toLowerCase().contains(query.toLowerCase());
    }

    private String highlight(String text, String query) {
        if (text == null || query == null || query.isBlank()) return text;
        Pattern pattern = Pattern.compile(Pattern.quote(query), Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE);
        Matcher matcher = pattern.matcher(text);
        return matcher.replaceAll("<mark>$0</mark>");
    }

    private List<String> extractOcrTexts(AnalysisResult ar) {
        List<String> result = new ArrayList<>();
        if (ar == null) return result;

        if (ar.getOcrResult() != null && !ar.getOcrResult().isBlank()) {
            try {
                List<Map<String, Object>> blocks = objectMapper.readValue(
                        ar.getOcrResult(),
                        new TypeReference<>() {}
                );
                for (Map<String, Object> block : blocks) {
                    Object textObj = block.get("text");
                    if (textObj instanceof String s && !s.isBlank()) {
                        result.add(s.trim());
                    }
                }
            } catch (Exception ignored) {
                // Если ocrResult не распарсился как массив, берём построчно
                String[] lines = ar.getOcrResult().split("\\r?\\n");
                for (String l : lines) {
                    if (!l.isBlank()) result.add(l.trim());
                }
            }
        }
        return result;
    }

    private record MatchHolder(
            Document doc,
            List<MatchedFieldDto> matchedFields,
            List<String> snippets,
            int relevanceScore
    ) {}
}

