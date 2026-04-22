"""
x1mvp Portfolio - CRM RAG Search System
Production-ready retrieval-augmented generation with vector search

Version: 3.0.0
Last Updated: 2026-01-15
"""

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

import asyncpg
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from pgvector.asyncpg import register_vector
from openai import AsyncOpenAI
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge

# Configure logging
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/crm",
    tags=["CRM RAG Search"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"}
    }
)

# ===============================================================================
# CONFIGURATION & MODELS
# ===============================================================================

@dataclass
class SearchResult:
    """Search result data model"""
    
    lead_name: str
    lead_company: str
    lead_role: str
    lead_email: Optional[str] = None
    lead_phone: Optional[str] = None
    source: str
    similarity_score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

@dataclass
class EmbeddingMetrics:
    """Embedding generation metrics"""
    
    model: str
    dimensions: int
    generation_time_ms: float
    token_count: int

class CRMConfig:
    """Configuration for CRM RAG system"""
    
    # Database configuration
    DATABASE_URL: str = os.getenv("PGVECTOR_URL", "")
    MAX_CONNECTIONS: int = int(os.getenv("MAX_DB_CONNECTIONS", "10"))
    CONNECTION_TIMEOUT: int = int(os.getenv("DB_TIMEOUT", "30"))
    
    # OpenAI configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gpt-4o-mini")
    
    # Search configuration
    DEFAULT_TOP_K: int = int(os.getenv("DEFAULT_TOP_K", "5"))
    MAX_TOP_K: int = int(os.getenv("MAX_TOP_K", "20"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    
    # Caching configuration
    ENABLE_CACHING: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour
    
    # Performance configuration
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Global configuration
CONFIG = CRMConfig()

# ===============================================================================
# PYDANTIC MODELS
# ===============================================================================

class SearchQuery(BaseModel):
    """Search query request model"""
    
    q: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="Search query for lead matching"
    )
    top_k: int = Field(
        default=5, 
        ge=1, 
        le=CONFIG.MAX_TOP_K,
        description="Number of results to return"
    )
    filters: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional filters for search results"
    )
    
    @validator('q')
    def validate_query(cls, v):
        """Validate search query"""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        
        # Check for potentially malicious content
        if len(v) > 1000:
            raise ValueError("Query too long (max 1000 characters)")
        
        # Remove excessive whitespace
        v = ' '.join(v.split())
        return v

class SearchResultItem(BaseModel):
    """Individual search result model"""
    
    lead_name: str
    lead_company: str
    lead_role: str
    lead_email: Optional[str] = None
    lead_phone: Optional[str] = None
    source: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    """Search response model"""
    
    demo: bool = Field(..., description="Whether this is a demo response")
    query: str = Field(..., description="Original search query")
    results: List[SearchResultItem] = Field(..., description="Search results")
    answer: Optional[str] = Field(None, description="Generated answer for full search")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Search metrics")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")

class DemoResponse(BaseModel):
    """Demo response model"""
    
    demo: bool = Field(..., description="Demo flag")
    leads: List[Dict[str, str]] = Field(..., description="Sample leads")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Demo metrics")

# ===============================================================================
# METRICS COLLECTION
# ===============================================================================

# Prometheus metrics
SEARCH_REQUESTS_TOTAL = Counter(
    'crm_search_requests_total',
    'Total CRM search requests',
    ['endpoint', 'status']
)

SEARCH_DURATION = Histogram(
    'crm_search_duration_seconds',
    'CRM search duration in seconds',
    ['endpoint']
)

EMBEDDING_GENERATION_TIME = Histogram(
    'crm_embedding_generation_time_seconds',
    'Time to generate embeddings'
)

DATABASE_QUERY_TIME = Histogram(
    'crm_database_query_time_seconds',
    'Database query time'
)

ACTIVE_CONNECTIONS = Gauge(
    'crm_active_database_connections',
    'Number of active database connections'
)

# ===============================================================================
# DATABASE MANAGER
# ===============================================================================

class DatabaseManager:
    """Manages PostgreSQL connection and vector operations"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self._initialize()
    
    async def _initialize(self):
        """Initialize database pool and Redis"""
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                CONFIG.DATABASE_URL,
                min_size=2,
                max_size=CONFIG.MAX_CONNECTIONS,
                command_timeout=CONFIG.CONNECTION_TIMEOUT
            )
            logger.info("✅ PostgreSQL pool created")
            
            # Test connection and register vector extension
            async with self.pool.acquire() as conn:
                await register_vector(conn)
                await conn.execute("SELECT 1")  # Test query
            logger.info("✅ pgvector extension registered")
            
            # Initialize Redis if enabled
            if CONFIG.ENABLE_CACHING:
                await self._initialize_redis()
            
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            raise RuntimeError(f"Database connection failed: {str(e)}")
    
    async def _initialize_redis(self):
        """Initialize Redis client for caching"""
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Redis connected for caching")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.redis_client = None
    
    async def search_similar_leads(
        self, 
        query_vector: List[float], 
        top_k: int = CONFIG.DEFAULT_TOP_K,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[SearchResult], EmbeddingMetrics]:
        """Search for similar leads using vector similarity"""
        
        start_time = time.time()
        
        async with self.pool.acquire() as conn:
            ACTIVE_CONNECTIONS.inc()
            
            try:
                # Build base query
                base_query = """
                    SELECT 
                        lead_name, 
                        lead_company, 
                        lead_role,
                        lead_email,
                        lead_phone,
                        source,
                        metadata,
                        1 - (embedding <=> $1) as similarity_score
                    FROM leads
                """
                
                # Add filters if provided
                where_clauses = []
                params = [query_vector, top_k]
                param_index = 3
                
                if filters:
                    if 'company' in filters:
                        where_clauses.append(f"lead_company ILIKE ${param_index}")
                        params.append(f"%{filters['company']}%")
                        param_index += 1
                    
                    if 'role' in filters:
                        where_clauses.append(f"lead_role ILIKE ${param_index}")
                        params.append(f"%{filters['role']}%")
                        param_index += 1
                
                if where_clauses:
                    base_query += " WHERE " + " AND ".join(where_clauses)
                
                # Complete query
                base_query += """
                    ORDER BY embedding <=> $1
                    LIMIT $2
                """
                
                # Execute query
                query_start = time.time()
                rows = await conn.fetch(base_query, *params)
                query_time = (time.time() - query_start) * 1000
                
                DATABASE_QUERY_TIME.observe(query_time / 1000)
                
                # Convert to SearchResult objects
                results = []
                for row in rows:
                    result = SearchResult(
                        lead_name=row['lead_name'],
                        lead_company=row['lead_company'],
                        lead_role=row['lead_role'],
                        lead_email=row['lead_email'],
                        lead_phone=row['lead_phone'],
                        source=row['source'],
                        similarity_score=float(row['similarity_score']),
                        metadata=json.loads(row['metadata']) if row['metadata'] else None
                    )
                    results.append(result)
                
                # Create metrics
                metrics = EmbeddingMetrics(
                    model=CONFIG.EMBEDDING_MODEL,
                    dimensions=len(query_vector),
                    generation_time_ms=0.0,  # Set by caller
                    token_count=0  # Set by caller
                )
                
                total_time = (time.time() - start_time) * 1000
                logger.info(f"Vector search completed: {len(results)} results in {total_time:.2f}ms")
                
                return results, metrics
                
            finally:
                ACTIVE_CONNECTIONS.dec()
    
    async def get_random_leads(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get random leads for demo"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT lead_name, lead_company, lead_role, source
                FROM leads 
                ORDER BY random() 
                LIMIT $1
                """,
                limit
            )
            return [dict(row) for row in rows]
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_leads,
                    COUNT(DISTINCT lead_company) as unique_companies,
                    COUNT(DISTINCT source) as sources
                FROM leads
            """)
            
            return {
                "total_leads": stats['total_leads'],
                "unique_companies": stats['unique_companies'],
                "sources": stats['sources'],
                "vector_dimensions": 1536,  # For text-embedding-3-large
                "active_connections": self.pool.get_size(),
                "idle_connections": self.pool.get_idle_size()
            }
    
    async def close(self):
        """Close database connections"""
        if self.pool:
            await self.pool.close()
        if self.redis_client:
            await self.redis_client.close()

# ===============================================================================
# OPENAI CLIENT MANAGER
# ===============================================================================

class OpenAIClientManager:
    """Manages OpenAI API interactions"""
    
    def __init__(self):
        if not CONFIG.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY environment variable is required")
        
        self.client = AsyncOpenAI(api_key=CONFIG.OPENAI_API_KEY)
    
    async def generate_embedding(self, text: str) -> Tuple[List[float], Dict[str, Any]]:
        """Generate embedding for search query"""
        start_time = time.time()
        
        try:
            response = await self.client.embeddings.create(
                model=CONFIG.EMBEDDING_MODEL,
                input=text
            )
            
            embedding = response.data[0].embedding
            generation_time = (time.time() - start_time) * 1000
            
            metrics = {
                "model": CONFIG.EMBEDDING_MODEL,
                "dimensions": len(embedding),
                "generation_time_ms": generation_time,
                "token_count": response.usage.total_tokens if hasattr(response, 'usage') else 0
            }
            
            EMBEDDING_GENERATION_TIME.observe(generation_time / 1000)
            
            return embedding, metrics
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {str(e)}")
    
    async def generate_answer(
        self, 
        query: str, 
        search_results: List[SearchResult],
        max_tokens: int = 300
    ) -> str:
        """Generate answer using ChatGPT based on search results"""
        
        # Format search results for the prompt
        lead_list = "\n".join([
            f"- {result.lead_name} ({result.lead_company}, {result.lead_role}) "
            f"[Score: {result.similarity_score:.3f}]"
            for result in search_results
        ])
        
        # Create prompt
        prompt = f"""You are a professional sales assistant. A user asked:

"{query}"

Here are the most relevant leads from our CRM database:
{lead_list}

Provide a concise, helpful answer that:
1. Identifies the best-matching leads
2. Explains why they're relevant
3. Suggests next steps

Answer in 2-3 sentences, focusing on actionable insights."""
        
        try:
            response = await self.client.chat.completions.create(
                model=CONFIG.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful sales assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=max_tokens
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")

# ===============================================================================
# RAG ENGINE
# ===============================================================================

class RAGEngine:
    """Retrieval-Augmented Generation engine for CRM search"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.openai_client = OpenAIClientManager()
        self.request_count = 0
    
    async def search_demo(self, limit: int = 3) -> DemoResponse:
        """Generate demo response with random leads"""
        try:
            start_time = time.time()
            
            # Get random leads
            leads = await self.db_manager.get_random_leads(limit)
            
            processing_time = (time.time() - start_time) * 1000
            
            return DemoResponse(
                demo=True,
                leads=leads,
                metrics={
                    "lead_count": len(leads),
                    "processing_time_ms": processing_time,
                    "database_stats": await self.db_manager.get_database_stats()
                }
            )
            
        except Exception as e:
            logger.error(f"Demo search failed: {e}")
            raise HTTPException(status_code=500, detail="Demo search failed")
    
    async def search_full(self, query: SearchQuery) -> SearchResponse:
        """Perform full RAG search with LLM answer"""
        try:
            start_time = time.time()
            self.request_count += 1
            
            # Check cache first
            cache_key = f"search:{hash(query.q)}:{query.top_k}"
            cached_result = None
            
            if CONFIG.ENABLE_CACHING and self.db_manager.redis_client:
                cached_data = await self.db_manager.redis_client.get(cache_key)
                if cached_data:
                    cached_result = SearchResponse.parse_raw(cached_data)
                    logger.info(f"Cache hit for query: {query.q[:50]}...")
            
            if cached_result:
                SEARCH_REQUESTS_TOTAL.labels(endpoint="full", status="cache_hit").inc()
                return cached_result
            
            # Step 1: Generate embedding
            query_vector, embedding_metrics = await self.openai_client.generate_embedding(query.q)
            
            # Step 2: Vector search
            search_results, _ = await self.db_manager.search_similar_leads(
                query_vector=query_vector,
                top_k=query.top_k,
                filters=query.filters
            )
            
            # Step 3: Generate answer
            answer = await self.openai_client.generate_answer(query.q, search_results)
            
            # Step 4: Build response
            processing_time = (time.time() - start_time) * 1000
            
            response = SearchResponse(
                demo=False,
                query=query.q,
                results=[
                    SearchResultItem(
                        lead_name=result.lead_name,
                        lead_company=result.lead_company,
                        lead_role=result.lead_role,
                        lead_email=result.lead_email,
                        lead_phone=result.lead_phone,
                        source=result.source,
                        similarity_score=result.similarity_score,
                        metadata=result.metadata
                    )
                    for result in search_results
                ],
                answer=answer,
                metrics={
                    "embedding": embedding_metrics,
                    "result_count": len(search_results),
                    "request_count": self.request_count,
                    "database_stats": await self.db_manager.get_database_stats()
                },
                processing_time_ms=processing_time
            )
            
            # Cache result
            if CONFIG.ENABLE_CACHING and self.db_manager.redis_client:
                await self.db_manager.redis_client.setex(
                    cache_key, 
                    CONFIG.CACHE_TTL, 
                    response.json()
                )
            
            SEARCH_REQUESTS_TOTAL.labels(endpoint="full", status="success").inc()
            SEARCH_DURATION.observe(processing_time / 1000)
            
            logger.info(f"Full search completed: {len(search_results)} results in {processing_time:.2f}ms")
            
            return response
            
        except Exception as e:
            SEARCH_REQUESTS_TOTAL.labels(endpoint="full", status="error").inc()
            logger.error(f"Full search failed: {e}")
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for RAG engine"""
        try:
            # Test database connection
            db_stats = await self.db_manager.get_database_stats()
            
            # Test OpenAI connection
            test_embedding, _ = await self.openai_client.generate_embedding("test")
            
            return {
                "status": "healthy",
                "database_connected": bool(db_stats),
                "openai_connected": len(test_embedding) > 0,
                "request_count": self.request_count,
                "configuration": {
                    "embedding_model": CONFIG.EMBEDDING_MODEL,
                    "chat_model": CONFIG.CHAT_MODEL,
                    "default_top_k": CONFIG.DEFAULT_TOP_K
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Global RAG engine
rag_engine = RAGEngine()

# ===============================================================================
# API ENDPOINTS
# ===============================================================================

def get_authentication(pwd: str = Header(..., alias="X-API-Key")) -> bool:
    """Simple API key authentication"""
    if pwd != os.getenv("API_PASSWORD", "demo2026"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

@router.post(
    "/demo",
    response_model=DemoResponse,
    summary="Demo Search",
    description="Get sample leads for demonstration purposes",
    tags=["Demo"]
)
async def demo_search(
    query: SearchQuery,
    _: bool = Depends(get_authentication)
) -> DemoResponse:
    """
    Demo endpoint that returns random leads without actual search.
    Useful for testing and showcasing the interface.
    """
    try:
        # Validate query (for consistency with full endpoint)
        _ = query.q  # This will trigger validation
        
        # Generate demo response
        demo_response = await rag_engine.search_demo()
        
        # Include original query in metadata
        demo_response.metrics["original_query"] = query.q
        
        return demo_response
        
    except Exception as e:
        logger.error(f"Demo endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Demo search failed")

@router.post(
    "/full",
    response_model=SearchResponse,
    summary="Full RAG Search",
    description="Complete RAG search with vector similarity and LLM answer",
    tags=["Search"]
)
async def full_search(
    query: SearchQuery,
    _: bool = Depends(get_authentication)
) -> SearchResponse:
    """
    Full search endpoint using RAG (Retrieval-Augmented Generation).
    Combines vector search with LLM-powered answer generation.
    """
    return await rag_engine.search_full(query)

@router.get(
    "/health",
    summary="Health Check",
    description="Check CRM RAG service health",
    tags=["Health"]
)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring"""
    return await rag_engine.health_check()

@router.get(
    "/stats",
    summary="Service Statistics",
    description="Get detailed service statistics",
    tags=["Monitoring"]
)
async def get_stats() -> Dict[str, Any]:
    """Get service statistics and configuration"""
    try:
        db_stats = await rag_engine.db_manager.get_database_stats()
        
        return {
            "service": "crm_rag_search",
            "version": "3.0.0",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": db_stats,
            "configuration": {
                "embedding_model": CONFIG.EMBEDDING_MODEL,
                "chat_model": CONFIG.CHAT_MODEL,
                "max_top_k": CONFIG.MAX_TOP_K,
                "similarity_threshold": CONFIG.SIMILARITY_THRESHOLD,
                "caching_enabled": CONFIG.ENABLE_CACHING,
                "cache_ttl": CONFIG.CACHE_TTL
            },
            "metrics": {
                "request_count": rag_engine.request_count,
                "active_connections": ACTIVE_CONNECTIONS._value.get()
            }
        }
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

# ===============================================================================
# EXCEPTION HANDLERS
# ===============================================================================

@router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging"""
    logger.warning(
        f"HTTP {exc.status_code}: {exc.detail} - "
        f"Request: {request.method} {request.url.path}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "path": request.url.path
        }
    )

@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(
        f"Unhandled exception: {str(exc)} - "
        f"Request: {request.method} {request.url.path}",
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )

# ===============================================================================
# CLEANUP
# ===============================================================================

async def cleanup():
    """Cleanup resources on shutdown"""
    await rag_engine.db_manager.close()
    logger.info("CRM RAG engine cleaned up")

# Export for testing
__all__ = [
    "router",
    "RAGEngine",
    "SearchResult",
    "SearchQuery",
    "SearchResponse",
    "cleanup"
]
