// Keep your existing API_CONFIG, but move it to config.js
// You can keep the one you already have in planets.json or use this simplified version

const API_CONFIG = {
    endpoints: {
        crm: {
            service: "CRM RAG Search",
            demo: "https://crm-demo.x1mvp.dev/demo",
            full: "https://crm-demo.x1mvp.dev/full",
            health: "https://crm-demo.x1mvp.dev/health"
        },
        fraud: {
            service: "Fraud Detection Stream", 
            demo: "https://fraud-demo.x1mvp.dev/demo",
            full: "https://fraud-demo.x1mvp.dev/full",
            health: "https://fraud-demo.x1mvp.dev/health"
        },
        clinical: {
            service: "Clinical Risk Predictor",
            demo: "https://clinical-demo.x1mvp.dev/demo",
            full: "https://clinical-demo.x1mvp.dev/full",
            health: "https://clinical-demo.x1mvp.dev/health"
        },
        nlp: {
            service: "NLP Text Classifier",
            demo: "https://nlp-demo.x1mvp.dev/demo", 
            full: "https://nlp-demo.x1mvp.dev/full",
            health: "https://nlp-demo.x1mvp.dev/health"
        }
    },
    settings: {
        fallbackToDemo: true,
        timeout: 5000,
        retries: 2
    },
    fallbacks: {
        simulatedOutputs: {
            crm: [
                { type: "info", text: "$ Initializing CRM RAG Search System..." },
                { type: "success", text: "✓ Connected to PostgreSQL (pgvector enabled)" },
                { type: "info", text: "✓ Loaded OpenAI embedding model" },
                { type: "info", text: "✓ Index ready: 10,485,762 records" },
                { type: "input", text: '> Query: "high-value enterprise clients"' },
                { type: "success", text: "✓ Found 47 matches (similarity > 0.85)" },
                { type: "output", text: "Top Results: Acme Corp ($2.4M ARR), TechStart Inc ($1.8M ARR)" },
                { type: "success", text: "✓ Query completed in 42ms" }
            ],
            fraud: [
                { type: "info", text: "$ Starting Fraud Detection Stream..." },
                { type: "success", text: "✓ Kafka brokers: 3 nodes online" },
                { type: "info", text: "✓ Spark Streaming: 8 executors ready" },
                { type: "info", text: "📊 Stream metrics: 6M events processed" },
                { type: "output", text: "• Throughput: 100,000 TPS" },
                { type: "output", text: "• Fraud detected: 1,247 (0.02%)" },
                { type: "warning", text: "⚠ Alert: Unusual pattern detected" },
                { type: "success", text: "✓ Stream running smoothly" }
            ],
            clinical: [
                { type: "info", text: "$ Initializing Clinical Risk Predictor..." },
                { type: "success", text: "✓ XGBoost model loaded (AUC: 0.89)" },
                { type: "info", text: "✓ SHAP explainer ready" },
                { type: "info", text: "✓ FHIR validation: PASSED" },
                { type: "input", text: "> Patient vitals input received..." },
                { type: "warning", text: "🏥 Risk Score: 0.73 (HIGH)" },
                { type: "output", text: "Top Risk Factors: Age (+0.18), BP (+0.15)" },
                { type: "success", text: "✓ Analysis completed in 89ms" }
            ],
            nlp: [
                { type: "info", text: "$ Initializing NLP Text Classifier..." },
                { type: "success", text: "✓ BERT-ONNX model loaded" },
                { type: "info", text: "✓ Redis cache: 1M+ entries" },
                { type: "input", text: '> Text: "scalable cloud data processing"' },
                { type: "success", text: "✓ Inference completed in 8ms" },
                { type: "output", text: "Top Categories:" },
                { type: "output", text: "1. Technology (0.94) ████████████" },
                { type: "output", text: "2. Business (0.87) ██████████" },
                { type: "success", text: "✓ Classification completed" }
            ]
        }
    }
};

// Initialize API client
window.API_CONFIG = API_CONFIG;

console.log('🔧 API Config loaded');
