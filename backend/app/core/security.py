"""Security management"""

import time
import hashlib
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class SecurityManager:
    """Manages API security and authentication"""
    
    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
        self.failed_attempts: Dict[str, List[float]] = {}
        self.rate_limits: Dict[str, List[float]] = {}
        self._initialize_api_keys()
    
    def _initialize_api_keys(self):
        """Initialize API keys from environment"""
        from .config import settings
        
        for key in settings.API_KEYS:
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            self.api_keys[key_hash] = {
                "created_at": time.time(),
                "last_used": None,
                "request_count": 0
            }
    
    def validate_api_key(self, api_key: str) -> bool:
        """Validate API key"""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        if key_hash not in self.api_keys:
            return False
        
        # Update usage statistics
        self.api_keys[key_hash]["last_used"] = time.time()
        self.api_keys[key_hash]["request_count"] += 1
        
        return True
    
    def is_rate_limited(self, identifier: str) -> bool:
        """Check if identifier is rate limited"""
        from .config import settings
        
        if not settings.ENABLE_RATE_LIMITING:
            return False
        
        now = time.time()
        window_start = now - settings.RATE_LIMIT_WINDOW
        
        # Clean old requests
        if identifier in self.rate_limits:
            self.rate_limits[identifier] = [
                req_time for req_time in self.rate_limits[identifier]
                if req_time > window_start
            ]
        else:
            self.rate_limits[identifier] = []
        
        # Check limit
        return len(self.rate_limits[identifier]) >= settings.RATE_LIMIT_REQUESTS
    
    def add_request(self, identifier: str):
        """Add request to rate limiter"""
        if identifier not in self.rate_limits:
            self.rate_limits[identifier] = []
        
        self.rate_limits[identifier].append(time.time())
