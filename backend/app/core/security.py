"""Security management"""

import os
import time
import hashlib
import logging
from typing import Any, Dict, List, Optional

from fastapi import Header

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages API security and authentication."""

    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
        self.failed_attempts: Dict[str, List[float]] = {}
        self.rate_limits: Dict[str, List[float]] = {}
        # ADMIN_KEY is validated at startup by Settings.validate(); no default here.
        raw_admin_keys = os.getenv("ADMIN_KEY", "")
        if not raw_admin_keys:
            raise RuntimeError(
                "ADMIN_KEY environment variable is not set. "
                "Refusing to start with no admin credentials."
            )
        self.admin_keys: set = set(raw_admin_keys.split(","))
        self._initialize_api_keys()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _initialize_api_keys(self) -> None:
        """Hash and register API keys from settings."""
        from .config import settings

        for key in settings.API_KEYS:
            key_hash = hashlib.sha256(key.encode()).hexdigest()
            self.api_keys[key_hash] = {
                "created_at": time.time(),
                "last_used": None,
                "request_count": 0,
            }

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate_demo(self, request) -> bool:
        """Demo endpoints: rate-limited but no API key required."""
        user_ip = request.client.host
        return not self.is_rate_limited(user_ip)

    def authenticate_full(
        self,
        api_key: str = Header(...),
        admin_key: str = Header(default=None),
    ) -> bool:
        """Full endpoints: require a valid API key; admin key bypasses rate limits."""
        if admin_key and admin_key in self.admin_keys:
            return True

        identifier = api_key
        if self._is_brute_force_locked(identifier):
            return False

        valid = self.validate_api_key(api_key)
        if not valid:
            self._record_failed_attempt(identifier)
        return valid

    # ------------------------------------------------------------------
    # API key management
    # ------------------------------------------------------------------

    def validate_api_key(self, api_key: str) -> bool:
        """Return True if the key is registered; update usage stats."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        if key_hash not in self.api_keys:
            return False
        self.api_keys[key_hash]["last_used"] = time.time()
        self.api_keys[key_hash]["request_count"] += 1
        return True

    # ------------------------------------------------------------------
    # Brute-force protection
    # ------------------------------------------------------------------

    def _record_failed_attempt(self, identifier: str) -> None:
        """Record a single failed authentication attempt."""
        self.failed_attempts.setdefault(identifier, []).append(time.time())

    def _is_brute_force_locked(
        self,
        identifier: str,
        window: int = 300,
        max_attempts: int = 5,
    ) -> bool:
        """
        Return True if *identifier* has exceeded *max_attempts* failed
        authentication attempts within the last *window* seconds.
        """
        now = time.time()
        cutoff = now - window
        recent = [t for t in self.failed_attempts.get(identifier, []) if t > cutoff]
        self.failed_attempts[identifier] = recent
        return len(recent) >= max_attempts

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def is_rate_limited(self, identifier: str) -> bool:
        """Return True if *identifier* has exceeded the configured request rate."""
        from .config import settings

        if not settings.ENABLE_RATE_LIMITING:
            return False

        now = time.time()
        window_start = now - settings.RATE_LIMIT_WINDOW
        recent = [t for t in self.rate_limits.get(identifier, []) if t > window_start]
        self.rate_limits[identifier] = recent
        return len(recent) >= settings.RATE_LIMIT_REQUESTS

    def add_request(self, identifier: str) -> None:
        """Record a request for rate-limit tracking."""
        self.rate_limits.setdefault(identifier, []).append(time.time())

    def get_rate_limit_status(self, service: str) -> Dict[str, Any]:
        """Return rate-limit metadata for *service*."""
        from .config import settings

        max_requests: int = settings.RATE_LIMIT_REQUESTS
        now = time.time()
        window_start = now - settings.RATE_LIMIT_WINDOW
        recent = [t for t in self.rate_limits.get(service, []) if t > window_start]

        oldest = recent[0] if recent else now
        reset_in = max(0, int(oldest + settings.RATE_LIMIT_WINDOW - now))

        return {
            "can_proceed": len(recent) < max_requests,
            "used": len(recent),
            "limit": max_requests,
            "reset_in": reset_in,
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def get_all_services() -> List[str]:
        return ["crm", "fraud", "clinical", "nlp"]
