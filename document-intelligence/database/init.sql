-- ====================================================================
-- Document Intelligence — Схема базы данных PostgreSQL
-- ====================================================================

-- Таблица 1: documents (Метаданные загруженных документов)
CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    document_type VARCHAR(64) NOT NULL DEFAULT 'UNKNOWN',
    original_filename VARCHAR(512) NOT NULL,
    stored_filename VARCHAR(512) NOT NULL UNIQUE,
    file_path VARCHAR(1024) NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    file_size BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'UPLOADED',
    overall_confidence DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Индексы для быстрого поиска документов
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_confidence ON documents(overall_confidence);


-- Таблица 2: document_fields (Извлечённые структурированные поля)
CREATE TABLE IF NOT EXISTS document_fields (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    field_name VARCHAR(128) NOT NULL,
    display_name VARCHAR(256),
    field_value TEXT,
    field_type VARCHAR(64) NOT NULL DEFAULT 'TEXT',
    confidence DOUBLE PRECISION DEFAULT 0.0,
    bbox TEXT,
    page_number INTEGER DEFAULT 1,
    validated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_document_fields_document
        FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE
);

-- Индексы для поиска по полям документов
CREATE INDEX IF NOT EXISTS idx_fields_document_id ON document_fields(document_id);
CREATE INDEX IF NOT EXISTS idx_fields_name ON document_fields(field_name);
CREATE INDEX IF NOT EXISTS idx_fields_type ON document_fields(field_type);


-- Таблица 3: analysis_results (Протоколы запусков AI-моделей)
CREATE TABLE IF NOT EXISTS analysis_results (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    analyzer_name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL,
    processing_time_ms DOUBLE PRECISION DEFAULT 0.0,
    detected_type VARCHAR(64),
    type_confidence DOUBLE PRECISION DEFAULT 0.0,
    raw_result TEXT,
    ocr_result TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_analysis_results_document
        FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE
);

-- Индексы для анализа моделей и аудита
CREATE INDEX IF NOT EXISTS idx_analysis_document_id ON analysis_results(document_id);
CREATE INDEX IF NOT EXISTS idx_analysis_analyzer_name ON analysis_results(analyzer_name);

