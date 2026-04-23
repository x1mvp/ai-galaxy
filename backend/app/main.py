from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _Limiter
from .core.config import Settings
from .core.security import get_rate_limit_status

# Rate limiting instances
demo_limiter = Limiter(rate=Settings.RATE_LIMIT_REQUESTS_DEMO, window=Settings.RATE_LIMIT_WINDOW)
full_limiter = Limiter(rate=Settings.RATE_LIMIT_REQUESTS_FULL, window=Settings.RATE_LIMIT_WINDOW)

def create_app() -> FastAPI:
    app = FastAPI(
        title=Settings.TITLE,
        description=Settings.DESCRIPTION,
        version=Settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"]
    )
    
    # Apply rate limiting to protected endpoints
    @app.middleware("http")
    async def add_rate_limit_headers(request: Request, call_next):
        # Check rate limit status
        if request.url.path.startswith("/api/v1/") and not request.url.path.endswith("/docs"):
            # Get the service name from URL
            path_parts = request.url.path.strip("/").split("/")
            if len(path_parts) >= 2:
                service = path_parts[1]
                if request.method == "POST":
                    limiter = full_limiter if request.url.path.endswith("/full") else demo_limiter
                    status = await get_rate_limit_status(service, limiter)
                    
                    if not status.can_proceed:
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": "Rate limit exceeded",
                                "limit": status.limit,
                                "reset": status.reset_in,
                                "retry-after": status.retry_after
                            }
                        )
        
        response = await call_next(request)
        return response
    
    return app

# Include routers
from . import crm, fraud, clinical, nlp

# Include routers with rate limiting
app.include_router(
    crm.router,
    prefix="/api/v1/crm",
    tags=["CRM"],
    dependencies=[Depends(demo_limiter)]
)

app.include_router(
    fraud.router,
    prefix="/api/v1/fraud", 
    tags=["Fraud"],
    dependencies=[Depends(full_limiter)]
)

app.include_router(
    clinical.router,
    prefix="/api/v1/clinical",
    tags=["Clinical"],
    dependencies=[Depends(full_limiter)]
)

app.include_router(
    nlp.router,
    prefix="/api/v1/nlp",
    tags=["NLP"],
    dependencies=[Depends(demo_limiter)]
)

# Health check
@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected" if get_database_url() else "disconnected",
        "redis": "connected" if get_redis_url() else "disconnected",
        "metrics_enabled": Settings.ENABLE_METRICS,
        "rate_limiting": {
            "demo_requests": Settings.RATE_LIMIT_REQUESTS_DEMO,
            "full_requests": Settings.RATE_LIMIT_REQUESTS_FULL,
            "window": Settings.RATE_LIMIT_WINDOW
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
