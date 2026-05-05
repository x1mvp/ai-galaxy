# app/exceptions.py
class NLPException(Exception):
    """Base NLP exception."""
    pass

class ModelLoadError(NLPException):
    """Model loading failed."""
    pass

class PredictionError(NLPException):
    """Prediction failed."""
    pass

class ValidationError(NLPException):
    """Input validation failed."""
    pass
