package com.docintell.repository;

import com.docintell.entity.DocumentVersion;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface DocumentVersionRepository extends JpaRepository<DocumentVersion, Long> {

    List<DocumentVersion> findByDocumentIdOrderByNumberDesc(Long documentId);

    Optional<DocumentVersion> findByDocumentIdAndNumber(Long documentId, Integer number);

    @Query("SELECT COALESCE(MAX(v.number), 0) FROM DocumentVersion v WHERE v.document.id = :documentId")
    int findMaxNumber(Long documentId);

    long countByDocumentId(Long documentId);

    void deleteByDocumentId(Long documentId);
}
