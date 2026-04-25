"""
Main FastAPI Application
Production-ready API with multiple service modules
"""

import os
import sys
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

# Add app directory to Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Import service routers
try:
    from app import crm, fraud, clinical, nlp
    ROUTERS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import service routers: {e}")
    ROUTERS_AVAILABLE = False

# Import configuration and utilities
try:
    from app.core.config import Settings
    from app.core.security import get_rate_limit_status
    from app.core.database import get_database_url, get_redis_url
    CONFIG_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import configuration: {e}")
    # Fallback configuration
    class Settings:
        TITLE = "Multi-Service API"
        DESCRIPTION = "Production-ready API with CRM, Fraud Detection, Clinical, and NLP services"
        VERSION = "1.0.0"
        RATE_LIMIT_REQUESTS_DEMO = 10
        RATE_LIMIT_REQUESTS_FULL = 5
        RATE_LIMIT_WINDOW = 60
        ENABLE_METRICS = True
    
    CONFIG_AVAILABLE = False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Custom rate limiting middleware"""
    
    def __init__(self, app, demo_requests=10, full_requests=5, window=60):
        super().__init__(app)
        self.demo_requests = demo_requests
        self.full_requests = full_requests
        self.window = window
        self.request_counts = {}
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for documentation endpoints
        if request.url.path in ["/docs", "/redoc", "/openapi.json", "/healthz"]:
            return await call_next(request)
        
        # Get client identifier
        client_id = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method
        
        # Simple in-memory rate limiting
        current_time = int(time.time())
        key = f"{client_id}:{path}"
        
        if key not in self.request_counts:
            self.request_counts[key] = []
        
        # Clean old requests outside the window
        self.request_counts[key] = [
            req_time for req_time in self.request_counts[key] 
            if current_time - req_time < self.window
        ]
        
        # Check rate limit
        limit = self.demo_requests
        if path.endswith("/full") or "fraud" in path or "clinical" in path:
            limit = self.full_requests
        
        if len(self.request_counts[key]) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window": self.window,
                    "retry-after": self.window
                }
            )
        
        # Add current request
        self.request_counts[key].append(current_time)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(self.request_counts[key])))
        response.headers["X-RateLimit-Reset"] = str(current_time + self.window)
        
        return response


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=Settings.TITLE,
        description=Settings.DESCRIPTION,
        version=Settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure appropriately for production
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )
    
    # Add rate limiting middleware
    app.add_middleware(
        RateLimitMiddleware,
        demo_requests=Settings.RATE_LIMIT_REQUESTS_DEMO,
        full_requests=Settings.RATE_LIMIT_REQUESTS_FULL,
        window=Settings.RATE_LIMIT_WINDOW
    )
    
    # Include service routers
    if ROUTERS_AVAILABLE:
        try:
            app.include_router(
                crm.router,
                prefix="/api/v1/crm",
                tags=["CRM"]
            )
            print("✅ CRM router included")
        except Exception as e:
            print(f"❌ Failed to include CRM router: {e}")
        
        try:
            app.include_router(
                fraud.router,
                prefix="/api/v1/fraud",
                tags=["Fraud Detection"]
            )
            print("✅ Fraud router included")
        except Exception as e:
            print(f"❌ Failed to include Fraud router: {e}")
        
        try:
            app.include_router(
                clinical.router,
                prefix="/api/v1/clinical",
                tags=["Clinical"]
            )
            print("✅ Clinical router included")
        except Exception as e:
            print(f"❌ Failed to include Clinical router: {e}")
        
        try:
            app.include_router(
                nlp.router,
                prefix="/api/v1/nlp",
                tags=["NLP"]
            )
            print("✅ NLP router included")
        except Exception as e:
            print(f"❌ Failed to include NLP router: {e}")
    else:
        print("⚠️  Service routers not available - running in minimal mode")
    
    @app.get("/healthz")
    async def health_check():
        """Comprehensive health check endpoint"""
        health_status = {
            "status": "healthy",
            "version": Settings.VERSION,
            "services": {
                "crm": ROUTERS_AVAILABLE,
                "fraud": ROUTERS_AVAILABLE,
                "clinical": ROUTERS_AVAILABLE,
                "nlp": ROUTERS_AVAILABLE
            },
            "configuration": {
                "metrics_enabled": Settings.ENABLE_METRICS,
                "rate_limiting": {
                    "demo_requests": Settings.RATE_LIMIT_REQUESTS_DEMO,
                    "full_requests": Settings.RATE_LIMIT_REQUESTS_FULL,
                    "window": Settings.RATE_LIMIT_WINDOW
                }
            }
        }
        
        # Add database status if available
        if CONFIG_AVAILABLE:
            try:
                health_status["database"] = "connected" if get_database_url() else "disconnected"
                health_status["redis"] = "connected" if get_redis_url() else "disconnected"
            except:
                health_status["database"] = "unknown"
                health_status["redis"] = "unknown"
        
        return health_status
    
    @app.get("/")
    async def root():
        """Root endpoint with basic information"""
        return {
            "message": "Multi-Service API",
            "version": Settings.VERSION,
            "docs": "/docs",
            "health": "/healthz",
            "services": [
                "/api/v1/crm",
                "/api/v1/fraud", 
                "/api/v1/clinical",
                "/api/v1/nlp"
            ] if ROUTERS_AVAILABLE else ["No services available"]
        }
    
    return app


# Create application instance
app = create_app()


# Run the application
if __name__ == "__main__":
    import time
    
    print(f"🚀 Starting {Settings.TITLE} v{Settings.VERSION}")
    print(f"📚 Documentation: http://localhost:8000/docs")
    print(f"🏥 Health Check: http://localhost:8000/healthz")
    
    if not ROUTERS_AVAILABLE:
        print("⚠️  Running in minimal mode - service routers not found")
        print("   Make sure the service modules are properly structured")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable for development
        log_level="info"
    )
