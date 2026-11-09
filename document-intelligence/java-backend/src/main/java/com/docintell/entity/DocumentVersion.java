package com.docintell.entity;

import jakarta.persistence.*;

import java.time.LocalDateTime;

/**
 * Версия содержимого документа в редакторе — аналог коммита.
 * Текст хранится как HTML редактора; номер растёт с 1 внутри документа.
 */
@Entity
@Table(name = "document_versions",
        uniqueConstraints = @UniqueConstraint(columnNames = {"document_id", "number"}),
        indexes = @Index(name = "idx_versions_document", columnList = "document_id"))
public class DocumentVersion {

    /** Откуда взялась версия. */
    public enum Source { IMPORT, MANUAL, REVIEW, REVERT }

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "document_id", nullable = false)
    private Document document;

    @Column(nullable = false)
    private Integer number;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, columnDefinition = "VARCHAR(20)")
    private Source source;

    @Column(length = 1000)
    private String description;

    @Column(name = "content_html", nullable = false, columnDefinition = "TEXT")
    private String contentHtml;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public Document getDocument() { return document; }
    public void setDocument(Document document) { this.document = document; }
    public Integer getNumber() { return number; }
    public void setNumber(Integer number) { this.number = number; }
    public Source getSource() { return source; }
    public void setSource(Source source) { this.source = source; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getContentHtml() { return contentHtml; }
    public void setContentHtml(String contentHtml) { this.contentHtml = contentHtml; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
