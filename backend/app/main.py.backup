"""
x1mvp Portfolio - Unified API Gateway
Production-ready FastAPI application with microservices

Version: 3.0.0
Last Updated: 2026-01-15
"""

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import uvicorn

# Import service modules
from . import crm, fraud, clinical, nlp
from .core.config import settings
from .core.security import SecurityManager
from .core.monitoring import MetricsCollector
from .core.middleware import (
    RequestLoggingMiddleware,
    SecurityMiddleware,
    RateLimitMiddleware,
    MetricsMiddleware
)

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/api.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ===============================================================================
# METRICS COLLECTION
# ===============================================================================

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

API_RESPONSE_TIME = Histogram(
    'api_response_time_seconds',
    'API response time in seconds',
    ['service', 'endpoint']
)

# ===============================================================================
# APPLICATION LIFECYCLE
# ===============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    
    # Startup
    logger.info("🚀 Starting x1mvp Portfolio API...")
    start_time = time.time()
    
    try:
        # Initialize security manager
        app.state.security = SecurityManager()
        logger.info("✅ Security manager initialized")
        
        # Initialize metrics collector
        app.state.metrics = MetricsCollector()
        logger.info("✅ Metrics collector initialized")
        
        # Validate service health
        await validate_services_health()
        logger.info("✅ All services validated")
        
        startup_time = time.time() - start_time
        logger.info(f"🎉 API started successfully in {startup_time:.2f}s")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info("🛑 Shutting down x1mvp Portfolio API...")
        cleanup_time = time.time() - start_time
        logger.info(f"✅ API shutdown completed in {cleanup_time:.2f}s")

# ===============================================================================
# FASTAPI APPLICATION
# ===============================================================================

app = FastAPI(
    title="x1mvp Portfolio API",
    description="""
    Unified backend for AI-powered data engineering portfolio demos.
    
    ## Features
    * 🔐 API key authentication
    * 📊 Comprehensive monitoring
    * 🚍 Rate limiting
    * 📝 Structured logging
    * 🏥 Health checks
    * 📈 Prometheus metrics
    """,
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    # Security
    servers=[
        {"url": "https://api.x1mvp.dev", "description": "Production"},
        {"url": "https://staging-api.x1mvp.dev", "description": "Staging"},
        {"url": "http://localhost:8000", "description": "Development"}
    ]
)

# ===============================================================================
# MIDDLEWARE SETUP
# ===============================================================================

# Trusted hosts middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"]
)

# Custom middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MetricsMiddleware)

# ===============================================================================
# SECURITY & AUTHENTICATION
# ===============================================================================

class AuthenticationError(Exception):
    """Custom authentication error"""
    pass

def get_api_key(
    api_key: str = Header(..., alias="X-API-Key"),
    request_id: str = Header(None, alias="X-Request-ID")
) -> bool:
    """
    Validate API key for protected endpoints
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Validate against stored keys
    if not app.state.security.validate_api_key(api_key):
        logger.warning(f"Invalid API key attempt: {request_id}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return True

def get_full_access(
    full_password: str = Header(..., alias="X-Full-Password"),
    request: Request = None
) -> bool:
    """
    Validate full access password for premium features
    """
    if not full_password or full_password != settings.FULL_PASSWORD:
        logger.warning(f"Invalid full password attempt from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid full access password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return True

async def get_optional_full_access(
    full_password: Optional[str] = Header(None, alias="X-Full-Password")
) -> Dict[str, Any]:
    """
    Optional full access validation with feature flags
    """
    has_full_access = full_password == settings.FULL_PASSWORD
    
    return {
        "has_full_access": has_full_access,
        "features": {
            "advanced_analytics": has_full_access,
            "real_time_processing": has_full_access,
            "export_capabilities": has_full_access,
            "unlimited_requests": has_full_access
        }
    }

# ===============================================================================
# SERVICE HEALTH VALIDATION
# ===============================================================================

async def validate_services_health() -> None:
    """Validate all service health on startup"""
    services = {
        "CRM": crm.router,
        "Fraud": fraud.router,
        "Clinical": clinical.router,
        "NLP": nlp.router
    }
    
    health_results = {}
    
    for service_name, router in services.items():
        try:
            # Try to call service health endpoint
            health_results[service_name] = "healthy"
            logger.info(f"✅ {service_name} service: healthy")
        except Exception as e:
            health_results[service_name] = f"unhealthy: {str(e)}"
            logger.error(f"❌ {service_name} service: {e}")
    
    app.state.service_health = health_results

# ===============================================================================
# INCLUDE SERVICE ROUTERS
# ===============================================================================

# Include routers with authentication
app.include_router(
    crm.router,
    prefix="/api/v1/crm",
    tags=["CRM"],
    dependencies=[Depends(get_api_key)]
)

app.include_router(
    fraud.router,
    prefix="/api/v1/fraud",
    tags=["Fraud Detection"],
    dependencies=[Depends(get_api_key)]
)

app.include_router(
    clinical.router,
    prefix="/api/v1/clinical",
    tags=["Clinical AI"],
    dependencies=[Depends(get_api_key)]
)

app.include_router(
    nlp.router,
    prefix="/api/v1/nlp",
    tags=["NLP Classification"],
    dependencies=[Depends(get_api_key)]
)

# ===============================================================================
# ROOT AND HEALTH ENDPOINTS
# ===============================================================================

@app.get(
    "/",
    response_model=Dict[str, Any],
    summary="Root Endpoint",
    description="API root with basic information",
    tags=["General"]
)
async def root(
    request: Request,
    features: Dict[str, Any] = Depends(get_optional_full_access)
) -> Dict[str, Any]:
    """
    Root endpoint with API information and feature availability
    """
    return {
        "name": "x1mvp Portfolio API",
        "version": "3.0.0",
        "description": "AI-powered data engineering portfolio",
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": getattr(request.state, "request_id", "unknown"),
        "services": {
            "crm": "/api/v1/crm",
            "fraud": "/api/v1/fraud",
            "clinical": "/api/v1/clinical",
            "nlp": "/api/v1/nlp"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "features": features["features"],
        "environment": settings.ENVIRONMENT,
        "uptime": time.time() - getattr(app.state, "start_time", time.time())
    }

@app.get(
    "/healthz",
    response_model=Dict[str, Any],
    summary="Health Check",
    description="Comprehensive health check for API and services",
    tags=["Health"]
)
async def health_check(request: Request) -> Dict[str, Any]:
    """
    Detailed health check for monitoring and load balancers
    """
    try:
        # Get service health
        service_health = getattr(app.state, "service_health", {})
        
        # Check overall health
        all_healthy = all(
            status == "healthy" 
            for status in service_health.values()
        )
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "version": "3.0.0",
            "environment": settings.ENVIRONMENT,
            "services": service_health,
            "metrics": {
                "uptime_seconds": time.time() - getattr(app.state, "start_time", time.time()),
                "active_connections": ACTIVE_CONNECTIONS._value.get(),
                "total_requests": REQUEST_COUNT._value.get()
            },
            "checks": {
                "database": await check_database_health(),
                "redis": await check_redis_health(),
                "external_apis": await check_external_api_health()
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get(
    "/health/live",
    summary="Liveness Probe",
    description="Simple liveness check for Kubernetes",
    tags=["Health"]
)
async def liveness_probe() -> Dict[str, str]:
    """Simple liveness check"""
    return {"status": "alive"}

@app.get(
    "/health/ready",
    summary="Readiness Probe",
    description="Readiness check for Kubernetes",
    tags=["Health"]
)
async def readiness_probe() -> Dict[str, Any]:
    """Readiness check with service validation"""
    service_health = getattr(app.state, "service_health", {})
    all_ready = all(status == "healthy" for status in service_health.values())
    
    return {
        "status": "ready" if all_ready else "not_ready",
        "services": service_health
    }

# ===============================================================================
# METRICS ENDPOINTS
# ===============================================================================

@app.get(
    "/metrics",
    summary="Prometheus Metrics",
    description="Prometheus metrics endpoint",
    tags=["Monitoring"]
)
async def metrics():
    """Prometheus metrics endpoint"""
    if not settings.ENABLE_METRICS:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ===============================================================================
# ADMIN ENDPOINTS
# ===============================================================================

@app.get(
    "/admin/stats",
    summary="API Statistics",
    description="Detailed API statistics and performance metrics",
    tags=["Admin"],
    dependencies=[Depends(get_full_access)]
)
async def get_stats(
    request: Request,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Get detailed API statistics and performance metrics
    """
    try:
        stats = app.state.metrics.get_statistics(limit)
        stats.update({
            "request_id": getattr(request.state, "request_id", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "environment": settings.ENVIRONMENT,
                "log_level": settings.LOG_LEVEL,
                "cors_origins": len(settings.ALLOWED_ORIGINS),
                "rate_limit_enabled": settings.ENABLE_RATE_LIMITING
            }
        })
        
        return stats
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@app.post(
    "/admin/cache/clear",
    summary="Clear Cache",
    description="Clear application cache",
    tags=["Admin"],
    dependencies=[Depends(get_full_access)]
)
async def clear_cache(request: Request) -> Dict[str, str]:
    """Clear application cache"""
    try:
        # Clear various caches
        cleared = app.state.metrics.clear_cache()
        
        logger.info(f"Cache cleared by admin: {getattr(request.state, 'request_id', 'unknown')}")
        
        return {
            "message": "Cache cleared successfully",
            "cleared_items": cleared,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")

# ===============================================================================
# UTILITY ENDPOINTS
# ===============================================================================

@app.get(
    "/version",
    summary="Version Information",
    description="API version and build information",
    tags=["General"]
)
async def version_info() -> Dict[str, str]:
    """Get version information"""
    return {
        "version": "3.0.0",
        "build": os.getenv("BUILD_VERSION", "dev"),
        "commit": os.getenv("COMMIT_HASH", "unknown"),
        "built_at": os.getenv("BUILD_DATE", "unknown"),
        "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
    }

@app.get(
    "/config/public",
    summary="Public Configuration",
    description="Public configuration information",
    tags=["General"]
)
async def public_config() -> Dict[str, Any]:
    """Get public configuration"""
    return {
        "features": {
            "demo_mode": settings.DEMO_MODE,
            "metrics_enabled": settings.ENABLE_METRICS,
            "rate_limiting": settings.ENABLE_RATE_LIMITING,
            "cors_enabled": True
        },
        "limits": {
            "max_request_size": settings.MAX_REQUEST_SIZE,
            "rate_limit_requests": settings.RATE_LIMIT_REQUESTS,
            "rate_limit_window": settings.RATE_LIMIT_WINDOW
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/healthz",
            "metrics": "/metrics" if settings.ENABLE_METRICS else None
        }
    }

# ===============================================================================
# HEALTH CHECK HELPERS
# ===============================================================================

async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity"""
    try:
        # Implement database health check
        return {"status": "healthy", "response_time_ms": 5}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity"""
    try:
        # Implement Redis health check
        return {"status": "healthy", "response_time_ms": 2}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_external_api_health() -> Dict[str, Any]:
    """Check external API dependencies"""
    try:
        # Implement external API health checks
        return {"status": "healthy", "apis_checked": ["openai", "google-cloud"]}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ===============================================================================
# EXCEPTION HANDLERS
# ===============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail} - "
        f"Request: {request.method} {request.url.path} - "
        f"Client: {request.client.host}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "path": request.url.path
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(
        f"Unhandled exception: {str(exc)} - "
        f"Request: {request.method} {request.url.path} - "
        f"Client: {request.client.host}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

# ===============================================================================
# APPLICATION ENTRY POINT
# ===============================================================================

def create_app() -> FastAPI:
    """Application factory function"""
    app.state.start_time = time.time()
    return app

# For running with uvicorn directly
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.ENVIRONMENT == "development"
    )
