# tests/test_model_manager.py
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from app.nlp import ModelManager, model_manager


class TestModelManager:
    
    @pytest.fixture
    def test_manager(self):
        """Create a test model manager."""
        return ModelManager(
            model_name="distilbert-base-uncased-finetuned-sst-2-english",
            task="sentiment-analysis",
        )
    
    def test_testing_mode_skip_load(self):
        """Test that loading is skipped in testing mode."""
        os.environ["TESTING"] = "1"
        manager = ModelManager()
        manager.load()
        assert manager.is_loaded is True
        assert manager._start_time is not None
        del os.environ["TESTING"]
    
    def test_load_failure(self, test_manager):
        """Test model loading failure handling."""
        with patch('transformers.pipeline', side_effect=Exception("Model not found")):
            with pytest.raises(RuntimeError, match="Model loading failed"):
                test_manager.load()
    
    @patch('transformers.pipeline')
    def test_successful_load(self, mock_pipeline, test_manager):
        """Test successful model loading."""
        mock_pipeline.return_value = Mock()
        test_manager.load()
        
        assert test_manager.is_loaded is True
        assert test_manager._model is not None
        mock_pipeline.assert_called_once()
    
    def test_predict_without_load(self, test_manager):
        """Test prediction fails when model not loaded."""
        with pytest.raises(RuntimeError, match="Model is not loaded"):
            test_manager.predict("test text")
    
    @patch('transformers.pipeline')
    def test_predict_single_text(self, mock_pipeline, test_manager):
        """Test single text prediction."""
        mock_model = Mock()
        mock_model.return_value = [{"label": "POSITIVE", "score": 0.9}]
        mock_pipeline.return_value = mock_model
        
        test_manager.load()
        result = test_manager.predict("I love this!")
        
        assert result == {"label": "POSITIVE", "prob": 0.9}
    
    @patch('transformers.pipeline')
    def test_predict_batch_text(self, mock_pipeline, test_manager):
        """Test batch text prediction."""
        mock_model = Mock()
        mock_model.return_value = [
            {"label": "POSITIVE", "score": 0.9},
            {"label": "NEGATIVE", "score": 0.8}
        ]
        mock_pipeline.return_value = mock_model
        
        test_manager.load()
        results = test_manager.predict(["I love this!", "I hate this!"])
        
        assert len(results) == 2
        assert results[0] == {"label": "POSITIVE", "prob": 0.9}
        assert results[1] == {"label": "NEGATIVE", "prob": 0.8}
    
    def test_get_stats(self, test_manager):
        """Test statistics collection."""
        test_manager.request_count = 10
        test_manager.total_inference_time = 5.0
        test_manager.error_count = 1
        test_manager._start_time = time.monotonic() - 100
        
        stats = test_manager.get_stats()
        
        assert stats["request_count"] == 10
        assert stats["error_count"] == 1
        assert stats["total_inference_time"] == 5.0
        assert "cache_info" in stats
        assert "memory_info" in stats
    
    def test_health_check(self, test_manager):
        """Test health check functionality."""
        test_manager.is_loaded = True
        test_manager._model = Mock()
        test_manager._model.return_value = [{"label": "POSITIVE", "score": 0.9}]
        
        health = test_manager.health_check()
        
        assert health["status"] == "healthy"
        assert "test_prediction" in health
    
    def test_thread_safety(self, test_manager):
        """Test thread safety of model operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def worker():
            try:
                # Simulate concurrent operations
                test_manager.load()
                result = test_manager.predict("test")
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = [threading.Thread(target=worker) for _ in range(5)]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"


class TestCachedPredict:
    """Test the caching functionality."""
    
    def test_cache_hit_miss(self):
        """Test cache hit/miss behavior."""
        from app.nlp import _cached_predict
        
        with patch.object(model_manager, 'predict') as mock_predict:
            mock_predict.return_value = [{"label": "POSITIVE", "prob": 0.9}]
            
            # First call should be a miss
            result1 = _cached_predict("test text")
            assert mock_predict.call_count == 1
            
            # Second call should be a hit
            result2 = _cached_predict("test text")
            assert mock_predict.call_count == 1  # No additional call
            
            assert result1 == result2
