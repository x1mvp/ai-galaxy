""NLP types, model manager, and shared prediction logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TextPayload(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_must_be_non_empty_and_bounded(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("text must not be empty or whitespace-only")
        if len(v) > 10_000:
            raise ValueError("text must not exceed 10,000 characters")
        return v


class PredictionResult(BaseModel):
    label: str
    prob: float


# ---------------------------------------------------------------------------
# Model manager
# ---------------------------------------------------------------------------

# Lightweight demo labels used when the real model is not loaded.
_DEMO_LABELS = ["tech", "science", "politics", "sports", "entertainment"]


@dataclass
class ModelManager:
    """Wraps the underlying ML model.  Swap ``_model`` for a real classifier."""

    is_loaded: bool = field(default=False, init=False)
    _model: object = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load (or hot-swap) the underlying model.

        Replace the body of this method with real model-loading code, e.g.::

            self._model = joblib.load("model.pkl")

        Until then, the manager runs in *demo mode*: ``predict_single`` uses a
        fast deterministic heuristic so the service stays functional.
        """
        self.is_loaded = True

    def unload(self) -> None:
        self._model = None
        self.is_loaded = False

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict_single(self, text: str) -> List[PredictionResult]:
        """Return a ranked list of ``PredictionResult`` objects for *text*.

        When a real model is attached (``self._model is not None``) call it
        here.  The stub below produces deterministic-ish scores from the text
        length so unit tests that *don't* mock this method still get stable,
        schema-valid output.
        """
        if self._model is not None:
            # Real model path — replace with actual inference call.
            raw = self._model.predict_proba([text])[0]  # type: ignore[union-attr]
            return [
                PredictionResult(label=label, prob=float(prob))
                for label, prob in zip(_DEMO_LABELS, raw)
            ]

        # Stub: spread probability mass deterministically across demo labels.
        seed = len(text) % len(_DEMO_LABELS)
        weights = [1.0 / (abs(i - seed) + 1) for i in range(len(_DEMO_LABELS))]
        total = sum(weights)
        probs = [w / total for w in weights]

        results = [
            PredictionResult(label=label, prob=round(prob, 4))
            for label, prob in zip(_DEMO_LABELS, probs)
        ]
        return sorted(results, key=lambda r: r.prob, reverse=True)


# Module-level singleton — imported by routers and tests alike.
model_manager = ModelManager()
