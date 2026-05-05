"""
app.nlp - Production-ready Model Manager using Hugging Face Transformers.
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union
import threading

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline,
    Pipeline,
)
from transformers.utils import logging as transformers_logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress transformers warnings in production
transformers_logging.set_verbosity_error()


class ModelManager:
    """
    Production-ready Model Manager with Hugging Face Transformers.
    
    Features:
    - Thread-safe model loading and inference
    - Configurable model and task selection
    - Error handling and logging
    - Metrics collection
    - GPU/CPU automatic device placement
    - Memory-efficient inference
    """
    
    def __init__(
        self,
        model_name: str = "cardiffnlp/twitter-roberta-base-sentiment-latest",
        task: str = "sentiment-analysis",
        device: Optional[str] = None,
        max_length: int = 512,
        batch_size: int = 16,
        cache_dir: Optional[str] = None,
    ) -> None:
        self.model_name = model_name
        self.task = task
        self.max_length = max_length
        self.batch_size = batch_size
        self.cache_dir = cache_dir
        
        # Thread safety
        self._lock = threading.RLock()
        self._model: Optional[Pipeline] = None
        self._tokenizer: Optional[Any] = None
        
        # Metrics
        self.is_loaded: bool = False
        self.request_count: int = 0
        self.total_inference_time: float = 0.0
        self._start_time: Optional[float] = None
        self.error_count: int = 0
        
        # Device configuration
        self.device = self._determine_device(device)
        
        logger.info(f"Initialized ModelManager with model: {model_name}, task: {task}, device: {self.device}")

    def _determine_device(self, device: Optional[str]) -> str:
        """Automatically determine the best device for inference."""
        if device:
            return device
            
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def load(self) -> None:
        """Load the model with error handling and logging."""
        if os.getenv("TESTING", "").lower() in ("1", "true", "yes"):
            logger.info("Running in testing mode - skipping model load")
            self.is_loaded = True
            self._start_time = time.monotonic()
            return

        with self._lock:
            if self.is_loaded:
                logger.info("Model already loaded")
                return

            try:
                logger.info(f"Loading model {self.model_name} on device {self.device}")
                
                # Load model and tokenizer
                self._model = pipeline(
                    task=self.task,
                    model=self.model_name,
                    device=0 if self.device == "cuda" else -1,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    cache_dir=self.cache_dir,
                )
                
                self._tokenizer = self._model.tokenizer
                
                self.is_loaded = True
                self._start_time = time.monotonic()
                
                logger.info(f"Model loaded successfully on {self.device}")
                
                # Log model info
                if hasattr(self._model.model, 'config'):
                    config = self._model.model.config
                    logger.info(f"Model config: {config.__class__.__name__}, vocab_size: {getattr(config, 'vocab_size', 'unknown')}")
                
            except Exception as e:
                logger.error(f"Failed to load model {self.model_name}: {str(e)}")
                self.error_count += 1
                raise RuntimeError(f"Model loading failed: {str(e)}") from e

    def unload(self) -> None:
        """Safely unload the model and free memory."""
        with self._lock:
            if self._model is not None:
                try:
                    # Clear CUDA cache if using GPU
                    if self.device == "cuda":
                        torch.cuda.empty_cache()
                    
                    self._model = None
                    self._tokenizer = None
                    self.is_loaded = False
                    self._start_time = None
                    
                    logger.info("Model unloaded successfully")
                except Exception as e:
                    logger.error(f"Error during model unloading: {str(e)}")
                    self.error_count += 1

    def predict(self, text: Union[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Run inference with proper error handling and metrics.
        
        Args:
            text: Input text or list of texts for batch processing
            
        Returns:
            List of prediction results with 'label' and 'prob' keys
        """
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded. Call load() first.")

        start_time = time.monotonic()
        
        try:
            with self._lock:
                # Convert single text to list for uniform processing
                if isinstance(text, str):
                    text = [text]
                
                # Batch processing for efficiency
                results = []
                for i in range(0, len(text), self.batch_size):
                    batch = text[i:i + self.batch_size]
                    
                    # Truncate if necessary
                    batch = [t[:self.max_length] if len(t) > self.max_length else t for t in batch]
                    
                    batch_results = self._model(batch)
                    
                    # Normalize output format
                    for result in batch_results:
                        if isinstance(result, dict) and 'label' in result and 'score' in result:
                            results.append({
                                'label': result['label'],
                                'prob': float(result['score'])
                            })
                        else:
                            # Handle different output formats
                            results.append(self._normalize_result(result))
                
                self.request_count += len(text)
                
            inference_time = time.monotonic() - start_time
            self.total_inference_time += inference_time
            
            logger.debug(f"Processed {len(text)} texts in {inference_time:.3f}s")
            
            return results if len(results) > 1 else results[0] if results else []
            
        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            self.error_count += 1
            raise RuntimeError(f"Prediction failed: {str(e)}") from e

    def _normalize_result(self, result: Any) -> Dict[str, float]:
        """Normalize different model output formats to consistent dict format."""
        if isinstance(result, dict):
            if 'label' in result and 'score' in result:
                return {'label': result['label'], 'prob': float(result['score'])}
            elif 'label' in result and 'confidence' in result:
                return {'label': result['label'], 'prob': float(result['confidence'])}
        
        # Fallback: try to extract label and probability from various formats
        return {
            'label': str(result.get('label', 'unknown')),
            'prob': float(result.get('score', result.get('confidence', 0.0)))
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive model statistics and metrics."""
        uptime = (
            time.monotonic() - self._start_time
            if self._start_time is not None
            else 0.0
        )
        
        cache = _cached_predict.cache_info()
        
        # Memory usage info
        memory_info = {}
        if self.device == "cuda" and torch.cuda.is_available():
            memory_info = {
                "cuda_allocated": f"{torch.cuda.memory_allocated() / 1024**3:.2f} GB",
                "cuda_reserved": f"{torch.cuda.memory_reserved() / 1024**3:.2f} GB",
                "cuda_max_allocated": f"{torch.cuda.max_memory_allocated() / 1024**3:.2f} GB",
            }
        
        avg_inference_time = (
            self.total_inference_time / self.request_count
            if self.request_count > 0
            else 0.0
        )
        
        return {
            "model_loaded": self.is_loaded,
            "model_name": self.model_name,
            "task": self.task,
            "device": self.device,
            "uptime": uptime,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_inference_time": avg_inference_time,
            "total_inference_time": self.total_inference_time,
            "requests_per_second": self.request_count / uptime if uptime > 0 else 0.0,
            "cache_info": {
                "currsize": cache.currsize,
                "maxsize": cache.maxsize,
                "hits": cache.hits,
                "misses": cache.misses,
                "hit_rate": cache.hits / (cache.hits + cache.misses) if (cache.hits + cache.misses) > 0 else 0.0,
            },
            "memory_info": memory_info,
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the model."""
        try:
            if not self.is_loaded:
                return {"status": "unhealthy", "reason": "Model not loaded"}
            
            # Test prediction with a simple input
            test_result = self.predict("Health check test")
            
            return {
                "status": "healthy",
                "test_prediction": test_result,
                "timestamp": time.time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "reason": str(e),
                "timestamp": time.time(),
            }


# Global model manager instance
model_manager = ModelManager()


@lru_cache(maxsize=1000)
def _cached_predict(text: str) -> tuple:
    """Cached prediction function for performance optimization."""
    return tuple(model_manager.predict(text))
