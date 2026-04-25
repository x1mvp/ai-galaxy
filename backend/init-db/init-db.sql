-- PostgreSQL + pgvector initialization for AI Galaxy
-- Run with: docker-compose exec postgres psql -U postgres -d portfolio -f /docker-entrypoint-initdb.d/init-db.sql

-- ============================================================
-- Extensions
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Schemas
-- ============================================================

CREATE SCHEMA IF NOT EXISTS crm;
CREATE SCHEMA IF NOT EXISTS fraud;
CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS nlp;

-- ============================================================
-- updated_at helper (shared by crm.leads and clinical.patients)
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- CRM — RAG Search
-- ============================================================

CREATE TABLE IF NOT EXISTS crm.leads (
    id           SERIAL PRIMARY KEY,
    lead_name    VARCHAR(255) NOT NULL,
    lead_company VARCHAR(255) NOT NULL,
    lead_role    VARCHAR(255),
    lead_email   VARCHAR(255),
    lead_phone   VARCHAR(50),
    source       VARCHAR(100),
    metadata     JSONB,
    embedding    vector(1536),
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- FIX 1 & 2: index name must NOT carry the schema prefix; ivfflat syntax is
--   (column operator_class) WITH (lists = N), not operator_class('column').
CREATE INDEX IF NOT EXISTS leads_embedding_idx
    ON crm.leads
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- FIX 8: keep updated_at current automatically.
CREATE OR REPLACE TRIGGER crm_leads_updated_at
    BEFORE UPDATE ON crm.leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- Fraud Detection
-- ============================================================

CREATE TABLE IF NOT EXISTS fraud.transactions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    amount          DECIMAL(10,2) NOT NULL,
    location        VARCHAR(100),
    device_type     VARCHAR(50),
    payment_method  VARCHAR(50),
    ip_address      INET,
    is_fraud        BOOLEAN DEFAULT FALSE,
    risk_score      DECIMAL(5,3),
    transaction_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata        JSONB
);

-- FIX 3: remove schema prefix from index names.
CREATE INDEX IF NOT EXISTS transactions_user_idx
    ON fraud.transactions (user_id);

CREATE INDEX IF NOT EXISTS transactions_time_idx
    ON fraud.transactions (transaction_time);

-- ============================================================
-- Clinical AI
-- ============================================================

CREATE TABLE IF NOT EXISTS clinical.patients (
    id             SERIAL PRIMARY KEY,
    age            FLOAT CHECK (age >= 0   AND age <= 120),
    systolic_bp    FLOAT CHECK (systolic_bp  >= 70  AND systolic_bp  <= 250),
    diastolic_bp   FLOAT CHECK (diastolic_bp >= 40  AND diastolic_bp <= 150),
    cholesterol    FLOAT CHECK (cholesterol  >= 100 AND cholesterol  <= 500),
    bmi            FLOAT CHECK (bmi >= 10 AND bmi <= 50),
    risk_score     DECIMAL(5,3),
    risk_level     VARCHAR(20),
    assessment     TEXT,
    recommendations TEXT[],
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- FIX 3 (continued): no schema prefix on index names.
CREATE INDEX IF NOT EXISTS patients_age_idx
    ON clinical.patients (age);

CREATE INDEX IF NOT EXISTS patients_risk_idx
    ON clinical.patients (risk_score);

-- FIX 8: auto-update updated_at.
CREATE OR REPLACE TRIGGER clinical_patients_updated_at
    BEFORE UPDATE ON clinical.patients
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- NLP Classifier
-- ============================================================

CREATE TABLE IF NOT EXISTS nlp.documents (
    id                SERIAL PRIMARY KEY,
    text_content      TEXT NOT NULL,
    predictions       JSONB,
    model_version     VARCHAR(50) DEFAULT 'bert-base-uncased-v1',
    confidence        DECIMAL(5,3),
    processing_time_ms INTEGER,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Sample data
-- ============================================================

-- FIX 5: values were transposed — lead_name is the person, lead_company the org.
INSERT INTO crm.leads
    (lead_name, lead_company, lead_role, lead_email, source, metadata)
VALUES
    ('John Doe', 'Acme Corp', 'CEO', 'john@acme.com', 'CRM System',
     '{"industry": "Technology", "company_size": "1000+"}');

INSERT INTO fraud.transactions
    (user_id, amount, location, device_type, payment_method,
     ip_address, is_fraud, risk_score, metadata)
VALUES
    (1001, 1250.75, 'NY', 'iOS', 'credit_card',
     '192.168.1.1', FALSE, 0.02, '{"source": "mobile_app"}');

INSERT INTO clinical.patients
    (age, systolic_bp, diastolic_bp, cholesterol, bmi,
     risk_score, risk_level, assessment, recommendations)
VALUES
    (45, 120.0, 80.0, 200.0, 25.0,
     0.25, 'low', 'Low risk patient with stable vitals.',
     ARRAY['Maintain healthy lifestyle']);

-- FIX 4: removed the extra NOW() argument — created_at has a DEFAULT.
INSERT INTO nlp.documents
    (text_content, predictions, model_version, confidence, processing_time_ms)
VALUES
    ('scalable cloud data processing',
     '{"labels": ["technology", "business", "cloud"], "confidence": [0.94, 0.87, 0.92]}',
     'bert-base-uncased-v1', 0.94, 12);

-- ============================================================
-- Permissions
-- ============================================================

-- Schema-level: allows the user to see objects inside each schema.
GRANT USAGE ON SCHEMA crm      TO postgres;
GRANT USAGE ON SCHEMA fraud    TO postgres;
GRANT USAGE ON SCHEMA clinical TO postgres;
GRANT USAGE ON SCHEMA nlp      TO postgres;

-- FIX 7: GRANT on the schema alone does NOT cover tables; grant table-level too.
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA crm      TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA fraud    TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA clinical TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA nlp      TO postgres;

-- Sequences (for SERIAL columns / INSERT with RETURNING id).
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA crm      TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA fraud    TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA clinical TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA nlp      TO postgres;
