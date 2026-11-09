package com.docintell.entity;

import com.docintell.enums.AnalysisStatus;
import com.docintell.enums.DocumentType;
import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * JPA Сущность: Document (Документ)
 *
 * Представляет запись в таблице `documents`.
 * Содержит метаданные загруженного файла, вычисленный статус и оценку уверенности.
 */
@Entity
@Table(name = "documents")
public class Document {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Enumerated(EnumType.STRING)
    @Column(name = "document_type", nullable = false, columnDefinition = "VARCHAR(50)")
    private DocumentType documentType = DocumentType.UNKNOWN;

    @Column(name = "original_filename", nullable = false)
    private String originalFilename;

    @Column(name = "stored_filename", nullable = false, unique = true)
    private String storedFilename;

    @Column(name = "file_path", nullable = false)
    private String filePath;

    @Column(name = "mime_type", nullable = false)
    private String mimeType;

    @Column(name = "file_size", nullable = false)
    private Long fileSize;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, columnDefinition = "VARCHAR(50)")
    private AnalysisStatus status = AnalysisStatus.UPLOADED;

    @Column(name = "overall_confidence")
    private Double overallConfidence = 0.0;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @OneToMany(mappedBy = "document", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    @JsonIgnore
    private List<DocumentField> fields = new ArrayList<>();

    @OneToMany(mappedBy = "document", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    @JsonIgnore
    private List<AnalysisResult> analysisResults = new ArrayList<>();

    /** Название документа для реестра (по умолчанию — из текста или имени файла). */
    @Column(name = "title", length = 500)
    private String title;

    /** Черновик редактора — автосохранение между версиями. */
    @Column(name = "draft_html", columnDefinition = "TEXT")
    @JsonIgnore
    private String draftHtml;

    @OneToMany(mappedBy = "document", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.LAZY)
    @JsonIgnore
    private List<DocumentVersion> versions = new ArrayList<>();

    /** Последняя проверка по правилам: JSON с находками и счётчики для реестра. */
    @Column(name = "check_json", columnDefinition = "TEXT")
    @JsonIgnore
    private String checkJson;

    @Column(name = "check_critical")
    private Integer checkCritical;

    @Column(name = "check_warning")
    private Integer checkWarning;

    @Column(name = "check_info")
    private Integer checkInfo;

    @Column(name = "checked_at")
    private LocalDateTime checkedAt;

    public Document() {
    }

    public String getCheckJson() { return checkJson; }
    public void setCheckJson(String checkJson) { this.checkJson = checkJson; }
    public Integer getCheckCritical() { return checkCritical; }
    public void setCheckCritical(Integer v) { this.checkCritical = v; }
    public Integer getCheckWarning() { return checkWarning; }
    public void setCheckWarning(Integer v) { this.checkWarning = v; }
    public Integer getCheckInfo() { return checkInfo; }
    public void setCheckInfo(Integer v) { this.checkInfo = v; }
    public LocalDateTime getCheckedAt() { return checkedAt; }
    public void setCheckedAt(LocalDateTime v) { this.checkedAt = v; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getDraftHtml() { return draftHtml; }
    public void setDraftHtml(String draftHtml) { this.draftHtml = draftHtml; }
    public List<DocumentVersion> getVersions() { return versions; }

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        this.updatedAt = LocalDateTime.now();
    }

    public void addField(DocumentField field) {
        fields.add(field);
        field.setDocument(this);
    }

    public void addAnalysisResult(AnalysisResult result) {
        analysisResults.add(result);
        result.setDocument(this);
    }

    // --- Геттеры и сеттеры ---

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public DocumentType getDocumentType() {
        return documentType;
    }

    public void setDocumentType(DocumentType documentType) {
        this.documentType = documentType;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public void setOriginalFilename(String originalFilename) {
        this.originalFilename = originalFilename;
    }

    public String getStoredFilename() {
        return storedFilename;
    }

    public void setStoredFilename(String storedFilename) {
        this.storedFilename = storedFilename;
    }

    public String getFilePath() {
        return filePath;
    }

    public void setFilePath(String filePath) {
        this.filePath = filePath;
    }

    public String getMimeType() {
        return mimeType;
    }

    public void setMimeType(String mimeType) {
        this.mimeType = mimeType;
    }

    public Long getFileSize() {
        return fileSize;
    }

    public void setFileSize(Long fileSize) {
        this.fileSize = fileSize;
    }

    public AnalysisStatus getStatus() {
        return status;
    }

    public void setStatus(AnalysisStatus status) {
        this.status = status;
    }

    public Double getOverallConfidence() {
        return overallConfidence;
    }

    public void setOverallConfidence(Double overallConfidence) {
        this.overallConfidence = overallConfidence;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(LocalDateTime updatedAt) {
        this.updatedAt = updatedAt;
    }

    public List<DocumentField> getFields() {
        return fields;
    }

    public void setFields(List<DocumentField> fields) {
        this.fields = fields;
    }

    public List<AnalysisResult> getAnalysisResults() {
        return analysisResults;
    }

    public void setAnalysisResults(List<AnalysisResult> analysisResults) {
        this.analysisResults = analysisResults;
    }
}

