package com.docintell.service;

import com.docintell.dto.EditorDtos.*;
import com.docintell.entity.Document;
import com.docintell.entity.DocumentVersion;
import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.docintell.exception.DocumentNotFoundException;
import com.docintell.repository.DocumentRepository;
import com.docintell.repository.DocumentVersionRepository;
import com.docintell.validation.FileValidator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.List;
import java.util.Locale;
import java.util.Objects;

/**
 * Редактор документов: импорт файла в редактируемый вид, черновик, версии, экспорт.
 *
 * Модель хранения: каждая сохранённая правка — отдельная версия (как коммит),
 * между версиями текст живёт в черновике документа (автосохранение).
 */
@Service
public class EditorService {

    private static final Logger logger = LoggerFactory.getLogger(EditorService.class);
    private static final int MAX_HTML_LENGTH = 20_000_000;

    private final DocumentRepository documentRepository;
    private final DocumentVersionRepository versionRepository;
    private final FileStorageService fileStorageService;
    private final FileValidator fileValidator;
    private final AiServiceClient aiServiceClient;
    private final com.fasterxml.jackson.databind.ObjectMapper objectMapper;

    public EditorService(DocumentRepository documentRepository, DocumentVersionRepository versionRepository,
                         FileStorageService fileStorageService, FileValidator fileValidator, AiServiceClient aiServiceClient,
                         com.fasterxml.jackson.databind.ObjectMapper objectMapper) {
        this.documentRepository = documentRepository;
        this.versionRepository = versionRepository;
        this.fileStorageService = fileStorageService;
        this.fileValidator = fileValidator;
        this.aiServiceClient = aiServiceClient;
        this.objectMapper = objectMapper;
    }

    /**
     * Проверка по правилам. Проверяется присланный текст (то, что сейчас в редакторе)
     * или текущее содержимое документа. Результат сохраняется для реестра и следующего открытия.
     */
    @Transactional
    public CheckResult check(Long id, String html, boolean deep) {
        Document doc = find(id);
        String text = html != null ? checkHtml(html) : currentHtml(doc);
        ensureIndexed();        // сверка с базой берёт тексты других документов из поискового индекса
        com.fasterxml.jackson.databind.JsonNode result = aiServiceClient.checkDocument(text, doc.getDocumentType().name(), id, deep);
        com.fasterxml.jackson.databind.JsonNode counts = result.path("counts");
        doc.setCheckJson(result.path("findings").toString());
        doc.setCheckCritical(counts.path("critical").asInt());
        doc.setCheckWarning(counts.path("warning").asInt());
        doc.setCheckInfo(counts.path("info").asInt());
        doc.setCheckedAt(java.time.LocalDateTime.now());
        documentRepository.save(doc);
        logger.info("Документ {} проверен: критично {}, замечаний {}, советов {}", id,
                doc.getCheckCritical(), doc.getCheckWarning(), doc.getCheckInfo());
        CheckResult saved = lastCheck(doc);
        return saved == null ? null : new CheckResult(saved.findings(), saved.critical(), saved.warning(), saved.info(), saved.checkedAt(),
                result.path("semantic").isMissingNode() ? null : result.get("semantic"),
                result.path("cross").isMissingNode() ? null : result.get("cross"));
    }

    private CheckResult lastCheck(Document doc) {
        if (doc.getCheckedAt() == null || doc.getCheckJson() == null) {
            return null;
        }
        try {
            return new CheckResult(objectMapper.readTree(doc.getCheckJson()), nz(doc.getCheckCritical()), nz(doc.getCheckWarning()),
                    nz(doc.getCheckInfo()), doc.getCheckedAt(), null, null);
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            logger.warn("Не удалось прочитать сохранённую проверку документа {}: {}", doc.getId(), e.getMessage());
            return null;
        }
    }

    private static int nz(Integer v) {
        return v == null ? 0 : v;
    }

    /** Загрузка файла: сохраняем оригинал, преобразуем в HTML и создаём версию 1. */
    @Transactional
    public EditorDocument importFile(MultipartFile file) {
        fileValidator.validate(file);
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException e) {
            throw new IllegalStateException("Не удалось прочитать загруженный файл", e);
        }
        // Сначала конвертация: если файл не читается, в базу ничего не попадёт
        ConvertedContent converted = aiServiceClient.convertForEditor(bytes, file.getOriginalFilename());

        FileStorageService.StoredFileMetadata stored = fileStorageService.store(file);
        Document doc = new Document();
        doc.setOriginalFilename(file.getOriginalFilename());
        doc.setStoredFilename(stored.storedFilename());
        doc.setFilePath(stored.fullPath());
        doc.setFileSize(file.getSize());
        doc.setMimeType(file.getContentType() != null ? file.getContentType() : "application/octet-stream");
        doc.setStatus(AnalysisStatus.UPLOADED);
        doc.setOverallConfidence(0.0);
        doc.setTitle(pickTitle(converted.title(), file.getOriginalFilename()));
        doc.setDocumentType(guessType(doc.getTitle() + " " + file.getOriginalFilename()));
        doc = documentRepository.save(doc);

        addVersion(doc, converted.html(), DocumentVersion.Source.IMPORT, "Загружен файл «" + file.getOriginalFilename() + "»");
        logger.info("Документ {} импортирован в редактор: «{}», тип {}", doc.getId(), doc.getTitle(), doc.getDocumentType());
        indexContent(doc, converted.html());
        autoCheck(doc, converted.html());
        return toEditorDocument(doc, converted.warnings());
    }

    /** Открыть документ в редакторе. Документы, загруженные до появления редактора, преобразуются при первом открытии. */
    @Transactional
    public EditorDocument open(Long id) {
        Document doc = find(id);
        List<String> warnings = List.of();
        if (versionRepository.countByDocumentId(id) == 0) {
            try {
                byte[] bytes = fileStorageService.loadAsResource(doc.getStoredFilename()).getContentAsByteArray();
                ConvertedContent converted = aiServiceClient.convertForEditor(bytes, doc.getOriginalFilename());
                if (doc.getTitle() == null) {
                    doc.setTitle(pickTitle(converted.title(), doc.getOriginalFilename()));
                }
                addVersion(doc, converted.html(), DocumentVersion.Source.IMPORT, "Загружен файл «" + doc.getOriginalFilename() + "»");
                warnings = converted.warnings();
                indexContent(doc, converted.html());
                autoCheck(doc, converted.html());
            } catch (IOException e) {
                throw new IllegalStateException("Исходный файл документа не найден", e);
            }
        }
        return toEditorDocument(doc, warnings);
    }

    @Transactional(readOnly = true)
    public List<RegistryItem> list() {
        return documentRepository.findAll().stream()
                .sorted((a, b) -> b.getUpdatedAt().compareTo(a.getUpdatedAt()))
                .map(this::registryItem)
                .toList();
    }

    private RegistryItem registryItem(Document d) {
        List<String> parties = d.getCounterparties() == null || d.getCounterparties().isBlank()
                ? List.of() : List.of(d.getCounterparties().split("; "));
        return new RegistryItem(d.getId(), titleOf(d), d.getDocumentType().name(), d.getDocumentType().getDisplayName(),
                d.getOriginalFilename(), d.getFileSize(), d.getCreatedAt(), d.getUpdatedAt(), versionRepository.findMaxNumber(d.getId()),
                d.getCheckCritical(), d.getCheckWarning(), d.getCheckInfo(), d.getCheckedAt(),
                d.getDocNumber(), d.getDocDate(), d.getAmount(), parties, d.getValidUntil());
    }

    // ------------------------------------------------------------------ поиск

    /**
     * Поиск по документам. Сначала фильтр по полям карточки (тип, период, контрагент, сумма),
     * затем — полнотекстовый поиск по оставшимся. Пустой запрос возвращает отфильтрованный список.
     */
    /** После старта сервера сверяем индекс в фоне: AI-сервис поднимается дольше, поэтому несколько попыток. */
    @org.springframework.context.event.EventListener(org.springframework.boot.context.event.ApplicationReadyEvent.class)
    public void syncIndexOnStartup() {
        Thread t = new Thread(() -> {
            for (int attempt = 0; attempt < 24 && !ensureIndexed(); attempt++) {
                try {
                    Thread.sleep(5000);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }, "search-index-sync");
        t.setDaemon(true);
        t.start();
    }

    @Transactional
    public List<SearchHit> search(String q, String mode, List<String> typeNames, java.time.LocalDate from, java.time.LocalDate to,
                                  String counterparty, Double minAmount, Double maxAmount) {
        ensureIndexed();
        List<Document> docs = documentRepository.findAll().stream()
                .filter(d -> typeNames == null || typeNames.isEmpty() || typeNames.contains(d.getDocumentType().getDisplayName()) || typeNames.contains(d.getDocumentType().name()))
                .filter(d -> from == null || (dateOf(d) != null && !dateOf(d).isBefore(from)))
                .filter(d -> to == null || (dateOf(d) != null && !dateOf(d).isAfter(to)))
                .filter(d -> counterparty == null || counterparty.isBlank()
                        || (d.getCounterparties() != null && d.getCounterparties().toLowerCase(Locale.ROOT).contains(counterparty.toLowerCase(Locale.ROOT))))
                .filter(d -> minAmount == null || (d.getAmount() != null && d.getAmount() >= minAmount))
                .filter(d -> maxAmount == null || (d.getAmount() != null && d.getAmount() <= maxAmount))
                .toList();
        java.util.Map<Long, Document> byId = new java.util.HashMap<>();
        docs.forEach(d -> byId.put(d.getId(), d));
        if (q == null || q.isBlank()) {
            return docs.stream().sorted((a, b) -> b.getUpdatedAt().compareTo(a.getUpdatedAt()))
                    .map(d -> new SearchHit(registryItem(d), 0, true, List.of())).toList();
        }
        if (docs.isEmpty()) {
            return List.of();
        }
        com.fasterxml.jackson.databind.JsonNode res = aiServiceClient.search(q, "sem".equals(mode) ? "sem" : "words",
                docs.stream().map(Document::getId).toList(), 50);
        List<SearchHit> hits = new java.util.ArrayList<>();
        for (com.fasterxml.jackson.databind.JsonNode r : res.path("results")) {
            Document d = byId.get(r.path("id").asLong());
            if (d == null) {
                continue;
            }
            List<SearchSnippet> snippets = new java.util.ArrayList<>();
            for (com.fasterxml.jackson.databind.JsonNode s : r.path("snippets")) {
                List<List<Integer>> marks = new java.util.ArrayList<>();
                s.path("highlights").forEach(h -> marks.add(List.of(h.get(0).asInt(), h.get(1).asInt())));
                snippets.add(new SearchSnippet(s.path("block").asInt(), s.path("text").asText(), s.path("prefix").asBoolean(),
                        s.path("suffix").asBoolean(), marks, s.path("start").asInt(), s.path("end").asInt()));
            }
            hits.add(new SearchHit(registryItem(d), r.path("score").asDouble(), r.path("exact").asBoolean(), snippets));
        }
        return hits;
    }

    // ------------------------------------------------------------------ ассистент

    /** Вопрос к базе: отдаём AI-сервису карточки всех документов, он отбирает, считает и формулирует ответ. */
    @Transactional
    public com.fasterxml.jackson.databind.JsonNode askAssistant(AssistantRequest request) {
        ensureIndexed();
        List<java.util.Map<String, Object>> cards = new java.util.ArrayList<>();
        // вопрос по одному открытому документу: карточки базы не нужны, текст AI-сервис берёт из индекса
        Long docId = request == null ? null : request.docId();
        for (Document d : docId != null ? List.<Document>of() : documentRepository.findAll()) {
            java.util.Map<String, Object> c = new java.util.HashMap<>();
            c.put("id", d.getId());
            c.put("title", titleOf(d));
            c.put("type", d.getDocumentType().name());
            c.put("typeName", d.getDocumentType().getDisplayName());
            c.put("number", d.getDocNumber());
            c.put("date", d.getDocDate() == null ? null : d.getDocDate().toString());
            c.put("created", d.getCreatedAt().toLocalDate().toString());
            c.put("amount", d.getAmount());
            c.put("counterparties", d.getCounterparties() == null || d.getCounterparties().isBlank()
                    ? List.of() : List.of(d.getCounterparties().split("; ")));
            c.put("validUntil", d.getValidUntil() == null ? null : d.getValidUntil().toString());
            c.put("critical", nz(d.getCheckCritical()));
            c.put("warning", nz(d.getCheckWarning()));
            c.put("checked", d.getCheckedAt() != null);
            cards.add(c);
        }
        return aiServiceClient.askAssistant(request == null ? "" : request.question(), request == null ? null : request.context(), cards, docId);
    }

    public com.fasterxml.jackson.databind.JsonNode assistantStatus() {
        return aiServiceClient.assistantStatus();
    }

    private static java.time.LocalDate dateOf(Document d) {
        return d.getDocDate() != null ? d.getDocDate() : d.getCreatedAt().toLocalDate();
    }

    private volatile boolean indexSynced = false;

    /**
     * Сверка поискового индекса с базой: удаляет лишнее, дозаливает недостающие документы.
     * Вызывается после старта сервера и перед первым поиском (AI-сервис мог перезапуститься).
     */
    public synchronized boolean ensureIndexed() {
        if (indexSynced) {
            return true;
        }
        try {
            List<Long> ids = documentRepository.findAll().stream().map(Document::getId)
                    .filter(id -> versionRepository.countByDocumentId(id) > 0).toList();
            com.fasterxml.jackson.databind.JsonNode res = aiServiceClient.syncIndex(ids);
            int added = 0;
            for (com.fasterxml.jackson.databind.JsonNode m : res.path("missing")) {
                Document d = find(m.asLong());
                indexContent(d, currentHtml(d));
                added++;
            }
            logger.info("Поисковый индекс сверен: удалено {}, добавлено {}", res.path("removed").asInt(), added);
            indexSynced = true;
        } catch (RuntimeException e) {
            logger.warn("Сверка поискового индекса не выполнена: {}", e.getMessage());
        }
        return indexSynced;
    }

    /** Индексирует текст для поиска и сохраняет извлечённые поля карточки. Ошибка индексации не мешает работе. */
    private void indexContent(Document doc, String html) {
        try {
            com.fasterxml.jackson.databind.JsonNode f = aiServiceClient.indexDocument(doc.getId(), titleOf(doc), html).path("fields");
            doc.setFieldsJson(f.toString());
            doc.setDocNumber(textOrNull(f, "number"));
            doc.setDocDate(dateOrNull(f, "date"));
            doc.setValidUntil(dateOrNull(f, "validUntil"));
            doc.setAmount(f.hasNonNull("amount") ? f.get("amount").asDouble() : null);
            List<String> parties = new java.util.ArrayList<>();
            f.path("counterparties").forEach(p -> parties.add(p.asText()));
            String joined = String.join("; ", parties);
            doc.setCounterparties(joined.length() > 1000 ? joined.substring(0, 1000) : joined);
            documentRepository.save(doc);
        } catch (RuntimeException e) {
            indexSynced = false;            // догоним при следующей сверке
            logger.warn("Индексация документа {} не выполнена: {}", doc.getId(), e.getMessage());
        }
    }

    private static String textOrNull(com.fasterxml.jackson.databind.JsonNode f, String key) {
        return f.hasNonNull(key) ? f.get(key).asText() : null;
    }

    private static java.time.LocalDate dateOrNull(com.fasterxml.jackson.databind.JsonNode f, String key) {
        try {
            return f.hasNonNull(key) ? java.time.LocalDate.parse(f.get(key).asText()) : null;
        } catch (java.time.format.DateTimeParseException e) {
            return null;
        }
    }

    /** Убрать документ из поискового индекса (при удалении). */
    public void removeFromIndex(Long id) {
        try {
            aiServiceClient.removeFromIndex(id);
        } catch (RuntimeException e) {
            indexSynced = false;
            logger.warn("Не удалось убрать документ {} из индекса: {}", id, e.getMessage());
        }
    }

    @Transactional
    public void saveDraft(Long id, String html) {
        Document doc = find(id);
        doc.setDraftHtml(checkHtml(html));
        documentRepository.save(doc);
    }

    @Transactional
    public VersionMeta saveVersion(Long id, SaveVersionRequest request) {
        Document doc = find(id);
        DocumentVersion.Source source = parseSource(request.source());
        String description = request.description() == null || request.description().isBlank()
                ? (source == DocumentVersion.Source.REVERT ? "Возврат к предыдущей версии" : "Ручная правка")
                : request.description().trim();
        DocumentVersion v = addVersion(doc, checkHtml(request.html()), source, description);
        doc.setDraftHtml(null);
        documentRepository.save(doc);
        indexContent(doc, v.getContentHtml());
        return meta(v);
    }

    @Transactional(readOnly = true)
    public VersionContent getVersion(Long id, Integer number) {
        DocumentVersion v = versionRepository.findByDocumentIdAndNumber(id, number)
                .orElseThrow(() -> new DocumentNotFoundException("Версия " + number + " документа " + id + " не найдена"));
        return new VersionContent(v.getNumber(), v.getSource().name(), v.getDescription(), v.getCreatedAt(), v.getContentHtml());
    }

    @Transactional
    public void rename(Long id, String title) {
        if (title == null || title.isBlank()) {
            return;
        }
        Document doc = find(id);
        doc.setTitle(title.trim().length() > 500 ? title.trim().substring(0, 500) : title.trim());
        documentRepository.save(doc);
        indexContent(doc, currentHtml(doc));       // название тоже участвует в поиске
    }

    /** DOCX из присланного HTML (то, что сейчас в редакторе) или из текущего содержимого. */
    @Transactional(readOnly = true)
    public byte[] exportDocx(Long id, ExportRequest request) {
        Document doc = find(id);
        String html = request != null && request.html() != null ? request.html() : currentHtml(doc);
        return aiServiceClient.exportDocx(html, titleOf(doc));
    }

    @Transactional(readOnly = true)
    public String titleOf(Long id) {
        return titleOf(find(id));
    }

    // ------------------------------------------------------------------

    /** Проверка сразу после загрузки. Если сервис анализа недоступен, документ всё равно сохраняется. */
    private void autoCheck(Document doc, String html) {
        try {
            check(doc.getId(), html, false);
        } catch (RuntimeException e) {
            logger.warn("Автопроверка документа {} не выполнена: {}", doc.getId(), e.getMessage());
        }
    }

    private Document find(Long id) {
        return documentRepository.findById(id).orElseThrow(() -> new DocumentNotFoundException(id));
    }

    private DocumentVersion addVersion(Document doc, String html, DocumentVersion.Source source, String description) {
        DocumentVersion v = new DocumentVersion();
        v.setDocument(doc);
        v.setNumber(versionRepository.findMaxNumber(doc.getId()) + 1);
        v.setSource(source);
        v.setDescription(description.length() > 1000 ? description.substring(0, 1000) : description);
        v.setContentHtml(html == null ? "" : html);
        return versionRepository.save(v);
    }

    private String currentHtml(Document doc) {
        if (doc.getDraftHtml() != null) {
            return doc.getDraftHtml();
        }
        return versionRepository.findByDocumentIdOrderByNumberDesc(doc.getId()).stream().findFirst()
                .map(DocumentVersion::getContentHtml).orElse("");
    }

    private EditorDocument toEditorDocument(Document doc, List<String> warnings) {
        List<DocumentVersion> versions = versionRepository.findByDocumentIdOrderByNumberDesc(doc.getId());
        String latest = versions.isEmpty() ? "" : versions.get(0).getContentHtml();
        boolean draft = doc.getDraftHtml() != null && !Objects.equals(doc.getDraftHtml(), latest);
        return new EditorDocument(doc.getId(), titleOf(doc), doc.getDocumentType().name(), doc.getDocumentType().getDisplayName(),
                doc.getOriginalFilename(), doc.getMimeType(), doc.getFileSize(), doc.getCreatedAt(), doc.getUpdatedAt(),
                draft ? doc.getDraftHtml() : latest, draft, versions.isEmpty() ? 0 : versions.get(0).getNumber(),
                versions.stream().map(this::meta).toList(), warnings == null ? List.of() : warnings, lastCheck(doc), fieldsOf(doc));
    }

    private com.fasterxml.jackson.databind.JsonNode fieldsOf(Document doc) {
        try {
            return doc.getFieldsJson() == null ? null : objectMapper.readTree(doc.getFieldsJson());
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            return null;
        }
    }

    private VersionMeta meta(DocumentVersion v) {
        return new VersionMeta(v.getNumber(), v.getSource().name(), v.getDescription(), v.getCreatedAt(),
                v.getContentHtml() == null ? 0 : v.getContentHtml().length());
    }

    private static String titleOf(Document d) {
        return d.getTitle() != null ? d.getTitle() : stripExtension(d.getOriginalFilename());
    }

    private static String pickTitle(String fromText, String filename) {
        if (fromText != null && !fromText.isBlank() && fromText.length() <= 160) {
            return fromText.trim();
        }
        return stripExtension(filename);
    }

    private static String stripExtension(String name) {
        if (name == null) {
            return "Документ";
        }
        int dot = name.lastIndexOf('.');
        return (dot > 0 ? name.substring(0, dot) : name).replace('_', ' ');
    }

    private static String checkHtml(String html) {
        if (html == null) {
            return "";
        }
        if (html.length() > MAX_HTML_LENGTH) {
            throw new IllegalArgumentException("Документ слишком большой для сохранения");
        }
        return html;
    }

    private static DocumentVersion.Source parseSource(String s) {
        try {
            return s == null ? DocumentVersion.Source.MANUAL : DocumentVersion.Source.valueOf(s.toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            return DocumentVersion.Source.MANUAL;
        }
    }

    /** Тип документа по названию и имени файла. Порядок важен: «доп. соглашение к договору» — не договор. */
    static DocumentType guessType(String text) {
        String t = text == null ? "" : text.toLowerCase(Locale.ROOT).replace('ё', 'е').replace('_', ' ');
        if (t.contains("соглашени") && (t.contains("доп") || t.contains("дополнительн"))) return DocumentType.SUPPLEMENTARY_AGREEMENT;
        if (t.contains("претензи")) return DocumentType.CLAIM;
        if (t.contains("бюджет")) return DocumentType.BUDGET;
        if (t.contains("приказ")) return DocumentType.ORDER;
        if (t.contains("служебн")) return DocumentType.MEMO;
        if (t.contains("регламент") || t.contains("положение о") || t.contains("инструкци")) return DocumentType.REGULATION;
        if (t.contains("техническое задание") || t.matches("(?s).*(^|[^а-яa-z])тз([^а-яa-z]|$).*")) return DocumentType.TECH_SPEC;
        if (t.contains("договор") || t.contains("контракт")) return DocumentType.CONTRACT;
        if (t.contains("счет на оплату") || t.matches("(?s).*(^|[^а-я])счет([^а-я]|$).*")) return DocumentType.INVOICE;
        if (t.matches("(?s).*(^|[^а-я])акт([^а-я]|$).*")) return DocumentType.ACT;
        if (t.contains("накладн")) return DocumentType.WAYBILL;
        return DocumentType.UNKNOWN;
    }
}
