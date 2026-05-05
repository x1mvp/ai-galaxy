"""
app/middleware.py - Custom middleware for performance monitoring and logging
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to track request performance and timing"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Get request info before processing
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            logger.error(f"Request failed: {method} {path} - Error: {str(e)}")
            raise
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log performance metrics
        logger.info(
            f"PERF: {method} {path} - "
            f"Status: {status_code} - "
            f"Time: {process_time:.3f}s - "
            f"Client: {client_host}"
        )
        
        # Add performance header to response
        response.headers["X-Process-Time"] = f"{process_time:.3f}"
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Detailed request/response logging middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        import uuid
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Log incoming request
        logger.info(
            f"REQ_START [{request_id}]: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'} "
            f"- Headers: {dict(request.headers)}"
        )
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Log successful response
            process_time = time.time() - start_time
            logger.info(
                f"REQ_END [{request_id}]: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - "
                f"Time: {process_time:.3f}s - "
                f"Size: {len(response.body) if hasattr(response, 'body') else 'unknown'} bytes"
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"REQ_ERROR [{request_id}]: {request.method} {request.url.path} - "
                f"Error: {str(e)} - "
                f"Time: {process_time:.3f}s"
            )
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Remove server header for security
        if "server" in response.headers:
            del response.headers["server"]
        
        return response
