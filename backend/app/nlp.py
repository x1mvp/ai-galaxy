"""
app.nlp - Model manager stub.

In CI (TESTING=1 or TESTING=true), load() is a no-op so no model file
or network access is required. In production, replace the body of load()
and predict() with your real model logic.
"""

from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any


class ModelManager:
    def __init__(self) -> None:
        self.is_loaded: bool = False
        self.request_count: int = 0
        self._start_time: float | None = None
        self._model: Any = None

    def load(self) -> None:
        """Load the model. Skipped entirely when TESTING env var is set."""
        if os.getenv("TESTING", "").lower() in ("1", "true", "yes"):
            self.is_loaded = True
            self._start_time = time.monotonic()
            return

        raise NotImplementedError(
            "Real model loading is not yet implemented. "
            "Set TESTING=1 to run in CI/test mode."
        )

    def unload(self) -> None:
        self._model = None
        self.is_loaded = False
        self._start_time = None

    def predict(self, text: str) -> list[dict]:
        """
        Run inference. Returns a list of dicts with 'label' and 'prob' keys.
        In TESTING mode this is never called directly — conftest patches it.
        """
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call load() first.")
        self.request_count += 1
        return []

    def get_stats(self) -> dict:
        uptime = (
            time.monotonic() - self._start_time
            if self._start_time is not None
            else 0.0
        )
        cache = _cached_predict.cache_info()
        return {
            "model_loaded": self.is_loaded,
            "uptime": uptime,
            "request_count": self.request_count,
            "cache_info": {
                "currsize": cache.currsize,
                "maxsize": cache.maxsize,
                "hits": cache.hits,
                "misses": cache.misses,
            },
        }


model_manager = ModelManager()


@lru_cache(maxsize=1000)
def _cached_predict(text: str) -> tuple:
    return tuple(model_manager.predict(text))
