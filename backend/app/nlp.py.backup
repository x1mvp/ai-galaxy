"""
backend/app/nlp.py
NLP model manager + APIRouter for text classification.

Original fixes retained:
  - Bare ModelConfig.validate() call removed from module level
  - TESTING env guard added to validate() and predict()

New fixes (this revision):
  C3  @lru_cache on instance method _cached_tokenize holds strong ref to
      self, prevents GC, and never hits because self is part of the cache key.
      Replaced with a module-level cached function.
  H1  @router.exception_handler() does not exist on APIRouter — moved to
      app level in main.py. Removed from this file entirely.
  M1  predict() returned {"score": ...} but PredictionResult expects "prob".
      Normalised to "prob" everywhere so Pydantic validation passes.
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import onnxruntime as ort
    from transformers import AutoTokenizer
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    ort = None
    AutoTokenizer = None

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/nlp",
    tags=["NLP Classification"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
        503: {"description": "Service unavailable"},
    },
)


# =============================================================================
# Configuration
# =============================================================================
class ModelConfig:
    MODEL_PATH = Path(os.getenv("ONNX_MODEL_PATH", "/app/models/bert.onnx"))
    TOKENIZER_PATH = Path(os.getenv("TOKENIZER_PATH", "/app/models/tokenizer"))
    TOKENIZER_NAME = os.getenv("TOKENIZER_NAME", "distilbert-base-uncased")
    MAX_LENGTH: int = int(os.getenv("NLP_MAX_LENGTH", "512"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "32"))
    CACHE_SIZE: int = int(os.getenv("CACHE_SIZE", "1000"))
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.1"))
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    LABELS = [
        "Technology", "Finance", "Healthcare",
        "Legal", "Marketing", "Science", "Politics", "Sports",
    ]

    @classmethod
    def validate(cls) -> None:
        """
        Check model file exists. Skipped when TESTING=true.
        Called only from ModelManager.load() — never at module level.
        """
        if os.getenv("TESTING", "false").lower() == "true":
            logger.info("TESTING=true: skipping model file validation")
            return
        if not cls.MODEL_PATH.exists():
            raise RuntimeError(
                f"ONNX model not found at {cls.MODEL_PATH}. "
                "See README for model conversion steps."
            )


# =============================================================================
# Data models
# =============================================================================
class TextPayload(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)

    @validator("text")
    def clean_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Text cannot be empty")
        return " ".join(v.split())


class PredictionResult(BaseModel):
    label: str
    # FIX M1: field is "prob" throughout — predict() previously returned
    # "score" which caused Pydantic ValidationError on every /full request.
    prob: float = Field(..., ge=0.0, le=1.0)

    @validator("prob")
    def round_prob(cls, v: float) -> float:
        return round(v, 3)


class ClassificationResponse(BaseModel):
    demo: bool
    predictions: List[PredictionResult]
    metadata: Optional[Dict[str, Any]] = None
    processing_time: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    cache_size: int
    uptime: float
    version: str


# =============================================================================
# FIX C3 — Module-level tokenizer cache
# @lru_cache on an instance method (self._cached_tokenize) keeps a strong
# reference to self, preventing garbage collection after unload(), and the
# cache never hits because `self` is part of every cache key.
# Module-level function is the correct pattern: tokenizer is passed as an
# argument and is hashable, self is never involved.
# =============================================================================
@lru_cache(maxsize=1000)
def _tokenize_cached(
    tokenizer: Any,
    text: str,
    max_length: int,
) -> Dict[str, Any]:
    """Cached tokenization — module level, no self reference."""
    return tokenizer(
        text,
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="np",
    )


# =============================================================================
# Model manager
# =============================================================================
class ModelManager:
    def __init__(self) -> None:
        self._session: Any = None
        self._tokenizer: Any = None
        self.is_loaded: bool = False
        self.start_time = time.time()
        self.request_count = 0

    def load(self) -> None:
        """Called once at server startup via lifespan. Never at import time."""
        ModelConfig.validate()   # returns immediately when TESTING=true

        if os.getenv("TESTING", "false").lower() == "true":
            self.is_loaded = True
            logger.info("TESTING=true: model marked loaded (mock mode)")
            return

        if not ONNX_AVAILABLE:
            raise RuntimeError("onnxruntime / transformers not installed")

        try:
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 4
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                str(ModelConfig.MODEL_PATH),
                providers=["CPUExecutionProvider"],
                sess_options=opts,
            )

            src = (
                str(ModelConfig.TOKENIZER_PATH)
                if ModelConfig.TOKENIZER_PATH.exists()
                else ModelConfig.TOKENIZER_NAME
            )
            self._tokenizer = AutoTokenizer.from_pretrained(src)
            self.is_loaded = True
            logger.info("Model and tokenizer loaded from %s", src)

        except Exception as exc:
            raise RuntimeError(f"Failed to load NLP model: {exc}") from exc

    def unload(self) -> None:
        self._session = None
        self._tokenizer = None
        self.is_loaded = False
        _tokenize_cached.cache_clear()   # clear module-level cache on shutdown
        logger.info("Model unloaded")

    def predict(self, text: str) -> List[Dict[str, Any]]:
        """
        Returns list of {"label": str, "prob": float}.

        FIX M1: previously returned "score" key. Now consistently uses "prob"
        to match the PredictionResult schema, avoiding Pydantic ValidationError
        on every /full classification request.
        """
        if os.getenv("TESTING", "false").lower() == "true":
            return [
                {"label": "Technology", "prob": 0.91},
                {"label": "Finance",    "prob": 0.72},
                {"label": "Healthcare", "prob": 0.55},
                {"label": "Legal",      "prob": 0.41},
                {"label": "Marketing",  "prob": 0.28},
            ]

        if not self.is_loaded or self._session is None:
            raise RuntimeError("Model is not loaded. Call load() first.")

        try:
            # Use module-level cached tokenizer (FIX C3)
            inputs = _tokenize_cached(
                self._tokenizer,
                text,
                ModelConfig.MAX_LENGTH,
            )
            outputs = self._session.run(None, dict(inputs))
            logits = outputs[0][0]
            exp = np.exp(logits - np.max(logits))
            probs = exp / exp.sum()

            results = [
                {"label": label, "prob": float(prob)}
                for label, prob in zip(ModelConfig.LABELS, probs)
                if prob >= ModelConfig.CONFIDENCE_THRESHOLD
            ]
            return sorted(results, key=lambda x: x["prob"], reverse=True)[: ModelConfig.TOP_K]

        except Exception as exc:
            logger.error("Prediction failed: %s", exc)
            raise RuntimeError(f"Prediction failed: {exc}") from exc

    def predict_batch(self, texts: List[str]) -> List[List[PredictionResult]]:
        if not self._session or not self._tokenizer:
            raise RuntimeError("Model not loaded")

        inputs = self._tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=ModelConfig.MAX_LENGTH,
            return_tensors="np",
        )
        logits = self._session.run(None, {k: v.astype(np.int64) for k, v in inputs.items()})[0]
        probs = 1 / (1 + np.exp(-logits))   # sigmoid for multi-label

        results = []
        for row in probs:
            top = sorted(
                [
                    PredictionResult(label=ModelConfig.LABELS[i], prob=float(row[i]))
                    for i in range(min(len(ModelConfig.LABELS), len(row)))
                    if row[i] >= ModelConfig.CONFIDENCE_THRESHOLD
                ],
                key=lambda x: x.prob,
                reverse=True,
            )[: ModelConfig.TOP_K]
            results.append(top)
        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "model_loaded": self.is_loaded,
            "uptime": time.time() - self.start_time,
            "request_count": self.request_count,
            "cache_info": _tokenize_cached.cache_info()._asdict(),
        }


# Module-level singleton — validate() NOT called here (FIX from previous audit)
model_manager = ModelManager()


# =============================================================================
# Routes
# =============================================================================
def _get_time() -> float:
    return time.time()


@router.post("/demo", response_model=ClassificationResponse, summary="Demo classification")
async def demo_classification(payload: TextPayload) -> ClassificationResponse:
    """Returns fast demo predictions without real inference."""
    return ClassificationResponse(
        demo=True,
        predictions=[
            PredictionResult(label="spam",  prob=0.87),
            PredictionResult(label="news",  prob=0.71),
            PredictionResult(label="tech",  prob=0.62),
        ],
        metadata={"text_length": len(payload.text)},
        processing_time=5.0,
    )


@router.post("/full", response_model=ClassificationResponse, summary="Full classification")
async def full_classification(
    payload: TextPayload,
    start: float = Depends(_get_time),
) -> ClassificationResponse:
    """Real classification using BERT ONNX model."""
    model_manager.request_count += 1
    try:
        raw = model_manager.predict(payload.text)
        # FIX M1: predict() now returns "prob" keys — direct unpack works
        predictions = [PredictionResult(**p) for p in raw]
        return ClassificationResponse(
            demo=False,
            predictions=predictions,
            metadata={
                "text_length": len(payload.text),
                "threshold": ModelConfig.CONFIDENCE_THRESHOLD,
            },
            processing_time=(time.time() - start) * 1000,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/batch", response_model=List[ClassificationResponse], summary="Batch classification")
async def batch_classification(texts: List[str]) -> List[ClassificationResponse]:
    if len(texts) > ModelConfig.BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch size exceeds maximum of {ModelConfig.BATCH_SIZE}",
        )

    if os.getenv("TESTING", "false").lower() == "true" or ModelConfig.DEMO_MODE:
        mock_preds = [
            PredictionResult(label="spam", prob=0.87),
            PredictionResult(label="news", prob=0.71),
        ]
        return [
            ClassificationResponse(demo=True, predictions=mock_preds, metadata={"index": i})
            for i in range(len(texts))
        ]

    preds_list = model_manager.predict_batch(texts)
    return [
        ClassificationResponse(demo=False, predictions=preds, metadata={"index": i})
        for i, preds in enumerate(preds_list)
    ]


@router.get("/health", response_model=HealthResponse, summary="NLP service health")
async def nlp_health() -> HealthResponse:
    stats = model_manager.get_stats()
    return HealthResponse(
        status="healthy" if stats["model_loaded"] else "unhealthy",
        model_loaded=stats["model_loaded"],
        cache_size=stats["cache_info"].get("currsize", 0),
        uptime=stats["uptime"],
        version="3.0.0",
    )


# FIX H1: @router.exception_handler() was removed from this file entirely.
# APIRouter has no exception_handler() method — calling it raised AttributeError
# at import time. Handlers are registered on the app instance in main.py.
