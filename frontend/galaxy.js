// Galaxy JavaScript - Complete Interactivity

class GalaxyController {
    constructor() {
        this.currentService = null;
        this.modal = null;
        this.terminal = null;
        this.particles = null;
        this.animationId = null;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.initParticles();
        this.startAnimations();
        console.log('🌌 AI Galaxy initialized');
    }
    
    setupEventListeners() {
        // Planet clicks
        document.querySelectorAll('.planet').forEach(planet => {
            planet.addEventListener('click', (e) => {
                const service = planet.dataset.service;
                this.openModal(service);
            });
        });
        
        // Modal close
        document.querySelector('.modal-close').addEventListener('click', () => {
            this.closeModal();
        });
        
        // Demo button
        document.getElementById('demoBtn').addEventListener('click', () => {
            this.runDemo();
        });
        
        // Premium button
        document.getElementById('premiumBtn').addEventListener('click', () => {
            this.runFullVersion();
        });
        
        // Password input
        const passwordInput = document.getElementById('passwordInput');
        passwordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.runFullVersion();
            }
        });
        
        // Close modal on background click
        document.getElementById('demoModal').addEventListener('click', (e) => {
            if (e.target.id === 'demoModal') {
                this.closeModal();
            }
        });
    }
    
    openModal(service) {
        this.currentService = service;
        const modal = document.getElementById('demoModal');
        const title = document.getElementById('modalTitle');
        
        // Set title based on service
        const titles = {
            crm: '🔍 CRM RAG Search',
            fraud: '⚡ Fraud Detection Stream',
            clinical: '🏥 Clinical Risk Predictor',
            nlp: '📝 NLP Text Classifier'
        };
        
        title.textContent = titles[service] || 'AI Demo';
        
        // Clear terminal
        const terminal = document.getElementById('terminal');
        terminal.innerHTML = '';
        
        // Show modal
        modal.classList.add('active');
        
        // Focus password input
        document.getElementById('passwordInput').focus();
    }
    
    closeModal() {
        const modal = document.getElementById('demoModal');
        modal.classList.remove('active');
        this.currentService = null;
    }
    
    async runDemo() {
        if (!this.currentService) return;
        
        const terminal = document.getElementById('terminal');
        terminal.innerHTML = '';
        
        // Show loading
        this.addTerminalLine('🔄 Loading demo...', 'info');
        
        // Get demo data from fallbacks (since backend isn't set up yet)
        const demoOutputs = {
            crm: [
                { type: "info", text: "$ Initializing CRM RAG Search System..." },
                { type: "success", text: "✓ Connected to PostgreSQL (pgvector enabled)" },
                { type: "info", text: "✓ Loaded OpenAI embedding model" },
                { type: "info", text: "✓ Index ready: 10,485,762 records" },
                { type: "input", text: '> Query: "high-value enterprise clients in California"' },
                { type: "info", text: "Converting query to 1538-dimensional vector..." },
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
        };
        
        const outputs = demoOutputs[this.currentService] || [];
        
        // Animate terminal output
        for (let i = 0; i < outputs.length; i++) {
            setTimeout(() => {
                const output = outputs[i];
                this.addTerminalLine(output.text, output.type);
            }, i * 300);
        }
    }
    
    runFullVersion() {
        const passwordInput = document.getElementById('passwordInput');
        const password = passwordInput.value.trim();
        
        if (!password) {
            this.addTerminalLine('⚠️ Please enter a password', 'warning');
            return;
        }
        
        if (password !== 'galaxy2026') {
            this.addTerminalLine('❌ Invalid password. Try: galaxy2026', 'error');
            return;
        }
        
        this.addTerminalLine('🔓 Password accepted! Running full version...', 'success');
        
        // Simulate full version with more detailed output
        setTimeout(() => {
            this.addTerminalLine('🚀 Initializing full AI capabilities...', 'info');
            this.addTerminalLine('📊 Processing with real models...', 'info');
            this.addTerminalLine('✨ Enhanced analytics enabled...', 'success');
            this.addTerminalLine('🎯 Full version ready!', 'success');
        }, 1000);
    }
    
    addTerminalLine(text, type = 'output') {
        const terminal = document.getElementById('terminal');
        const line = document.createElement('div');
        line.className = 'terminal-line';
        
        let className = 'terminal-output';
        let prefix = '';
        
        if (type === 'input') {
            className = 'terminal-prompt';
            prefix = '> ';
        } else if (type === 'success') {
            className = 'terminal-success';
        } else if (type === 'error') {
            className = 'terminal-error';
        } else if (type === 'info') {
            className = 'terminal-info';
        }
        
        line.innerHTML = `<span class="${className}">${prefix}${text}</span>`;
        terminal.appendChild(line);
        
        // Scroll to bottom
        terminal.scrollTop = terminal.scrollHeight;
    }
    
    initParticles() {
        const canvas = document.getElementById('particles');
        const ctx = canvas.getContext('2d');
        
        // Set canvas size
        const resizeCanvas = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };
        
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        
        // Create particles
        this.particles = [];
        const particleCount = 100;
        
        for (let i = 0; i < particleCount; i++) {
            this.particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: (Math.random() - 0.5) * 0.5,
                size: Math.random() * 2 + 0.5,
                opacity: Math.random() * 0.5 + 0.2
            });
        }
        
        // Animation loop
        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            // Update and draw particles
            this.particles.forEach(particle => {
                // Update position
                particle.x += particle.vx;
                particle.y += particle.vy;
                
                // Wrap around screen
                if (particle.x < 0) particle.x = canvas.width;
                if (particle.x > canvas.width) particle.x = 0;
                if (particle.y < 0) particle.y = canvas.height;
                if (particle.y > canvas.height) particle.y = 0;
                
                // Draw particle
                ctx.beginPath();
                ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0, 255, 204, ${particle.opacity})`;
                ctx.fill();
            });
            
            // Draw connections between nearby particles
            for (let i = 0; i < this.particles.length; i++) {
                for (let j = i + 1; j < this.particles.length; j++) {
                    const dx = this.particles[i].x - this.particles[j].x;
                    const dy = this.particles[i].y - this.particles[j].y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < 100) {
                        ctx.beginPath();
                        ctx.moveTo(this.particles[i].x, this.particles[i].y);
                        ctx.lineTo(this.particles[j].x, this.particles[j].y);
                        ctx.strokeStyle = `rgba(0, 255, 204, ${0.1 * (1 - distance / 100)})`;
                        ctx.stroke();
                    }
                }
            }
            
            this.animationId = requestAnimationFrame(animate);
        };
        
        animate();
    }
    
    startAnimations() {
        // Add floating animation to hero elements
        const hero = document.querySelector('.hero');
        if (hero) {
            hero.style.animation = 'fadeInUp 1s ease-out';
        }
        
        // Add staggered animation to planets
        const planets = document.querySelectorAll('.planet');
        planets.forEach((planet, index) => {
            setTimeout(() => {
                planet.style.animation = `fadeInUp 0.8s ease-out ${index * 0.2}s`;
            }, index * 200);
        });
    }
}

// Initialize galaxy when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.galaxy = new GalaxyController();
});
