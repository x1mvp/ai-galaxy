-- PostgreSQL + pgvector initialization for AI Galaxy
-- Run with: docker-compose exec postgres psql -U postgres -d portfolio -f /docker-entrypoint-initdb.d/init-db.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS crm;
CREATE SCHEMA IF NOT EXISTS fraud;
CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS nlp;

-- CRM RAG Search Schema
CREATE TABLE IF NOT EXISTS crm.leads (
    id SERIAL PRIMARY KEY,
    lead_name VARCHAR(255) NOT NULL,
    lead_company VARCHAR(255) NOT NULL,
    lead_role VARCHAR(255),
    lead_email VARCHAR(255),
    lead_phone VARCHAR(50),
    source VARCHAR(100),
    metadata JSONB,
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create vector index for semantic search
CREATE INDEX IF NOT EXISTS crm.leads_embedding_idx ON crm.leads USING ivfflat (vector_cosine_ops('embedding'));

-- Fraud Detection Schema
CREATE TABLE IF NOT EXISTS fraud.transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    location VARCHAR(100),
    device_type VARCHAR(50),
    payment_method VARCHAR(50),
    ip_address INET,
    is_fraud BOOLEAN DEFAULT FALSE,
    risk_score DECIMAL(5,3),
    transaction_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS fraud.transactions_user_idx ON fraud.transactions(user_id);
CREATE INDEX IF NOT EXISTS fraud.transactions_time_idx ON fraud.transactions(transaction_time);

-- Clinical AI Schema
CREATE TABLE IF NOT EXISTS clinical.patients (
    id SERIAL PRIMARY KEY,
    age FLOAT CHECK (age >= 0 AND age <= 120),
    systolic_bp FLOAT CHECK (systolic_bp >= 70 AND systolic_bp <= 250),
    diastolic_bp FLOAT CHECK (diastolic_bp >= 40 AND diastolic_bp <= 150),
    cholesterol FLOAT CHECK (cholesterol >= 100 AND cholesterol <= 500),
    bmi FLOAT CHECK (bmi >= 10 AND bmi <= 50),
    risk_score DECIMAL(5,3),
    risk_level VARCHAR(20),
    assessment TEXT,
    recommendations TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS clinical.patients_age_idx ON clinical.patients(age);
CREATE INDEX IF NOT EXISTS clinical.patients_risk_idx ON clinical.patients(risk_score);

-- NLP Classifier Schema
CREATE TABLE IF NOT EXISTS nlp.documents (
    id SERIAL PRIMARY KEY,
    text_content TEXT NOT NULL,
    predictions JSONB,
    model_version VARCHAR(50) DEFAULT 'bert-base-uncased-v1',
    confidence DECIMAL(5,3),
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Sample data for testing
INSERT INTO crm.leads (lead_name, lead_company, lead_role, lead_email, source, metadata) VALUES
('Acme Corp', 'TechCorp', 'CEO', 'john@acme.com', 'CRM System', '{"industry": "Technology", "company_size": "1000+"}');

INSERT INTO fraud.transactions (user_id, amount, location, device_type, payment_method, ip_address, is_fraud, risk_score, metadata) VALUES
(1001, 1250.75, 'NY', 'iOS', 'credit_card', '192.168.1.1', FALSE, 0.02, '{"source": "mobile_app"}');

INSERT INTO clinical.patients (age, systolic_bp, diastolic_bp, cholesterol, bmi, risk_score, risk_level, assessment, recommendations, created_at, updated_at) VALUES
(45, 120.0, 80.0, 200.0, 25.0, 0.25, 'low', 'Low risk patient with stable vitals.', ARRAY['Maintain healthy lifestyle'], NOW(), NOW());

INSERT INTO nlp.documents (text_content, predictions, model_version, confidence, processing_time_ms) VALUES
('scalable cloud data processing', 
    '{"labels": ["technology", "business", "cloud"], "confidence": [0.94, 0.87, 0.92]}',
    'bert-base-uncased-v1', 0.94, 12, NOW()
);

-- Grant permissions for API user
GRANT USAGE ON SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA crm TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA fraud TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA clinical TO postgres;
GRANT ALL PRIVILEGES ON SCHEMA nlp TO postgres;
