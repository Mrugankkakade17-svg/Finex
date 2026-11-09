-- =====================================================================
-- Task: S1-DAT-01
-- Catalog: finex_dev
-- Schema: ai
-- Purpose: AI / RAG data (documents, embeddings, conversations)
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS finex_dev.ai;

-- ---------------------------------------------------------------------
-- documents
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.ai.documents (
    doc_id          BIGINT GENERATED ALWAYS AS IDENTITY,
    title           STRING NOT NULL,
    content         STRING,
    doc_type        STRING,
    source          STRING,
    uploaded_by     BIGINT,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- document_chunks
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.ai.document_chunks (
    chunk_id        BIGINT GENERATED ALWAYS AS IDENTITY,
    doc_id          BIGINT NOT NULL,
    chunk_text      STRING NOT NULL,
    chunk_index     INT NOT NULL,
    token_count     INT,
    created_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- embeddings
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.ai.embeddings (
    embedding_id      BIGINT GENERATED ALWAYS AS IDENTITY,
    chunk_id          BIGINT NOT NULL,
    model_name        STRING NOT NULL,
    embedding_vector  STRING,
    dimensions        INT,
    created_at        TIMESTAMP
);

-- ---------------------------------------------------------------------
-- conversations
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.ai.conversations (
    conversation_id   BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id           BIGINT NOT NULL,
    title             STRING,
    status            STRING,
    created_at        TIMESTAMP,
    updated_at        TIMESTAMP
);

-- ---------------------------------------------------------------------
-- messages
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.ai.messages (
    message_id        BIGINT GENERATED ALWAYS AS IDENTITY,
    conversation_id   BIGINT NOT NULL,
    role              STRING NOT NULL,
    content           STRING NOT NULL,
    citations         STRING,
    created_at        TIMESTAMP
);
