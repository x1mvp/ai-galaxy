"""
x1mvp Portfolio - Real-Time Fraud Detection Stream
Production-grade streaming API with real-time fraud detection simulation

Version: 3.0.0
Last Updated: 2026-01-15
"""

import asyncio
import json
import logging
import random
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse
import redis.asyncio as redis
from prometheus_client import Counter, Histogram, Gauge

# Configure logging
logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(
    prefix="/fraud",
    tags=["Fraud Detection"],
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
class FraudEvent:
    """Fraud detection event data model"""
    
    timestamp: str
    event_id: str
    user_id: int
    amount: float
    location: str
    device_type: str
    payment_method: str
    ip_address: str
    risk_score: float
    label: str
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

@dataclass
class StreamMetrics:
    """Streaming metrics data model"""
    
    events_generated: int = 0
    fraud_events: int = 0
    legit_events: int = 0
    average_amount: float = 0.0
    peak_risk_score: float = 0.0
    start_time: float = time.time()
    connected_clients: int = 0

class FraudStreamConfig:
    """Configuration for fraud detection stream"""
    
    # Stream parameters
    BATCH_SIZE: int = 10
    BATCH_INTERVAL_MS: int = 1  # 10K events/second
    MAX_CONCURRENT_STREAMS: int = 100
    
    # Fraud detection parameters
    BASE_FRAUD_RATE: float = 0.02  # 2% base fraud rate
    AMOUNT_FRAUD_MULTIPLIER: float = 1.5  # Higher amounts = higher fraud risk
    LOCATION_FRAUD_RATES: Dict[str, float] = {
        "NY": 0.025, "LA": 0.018, "SF": 0.022, 
        "CHI": 0.020, "MIA": 0.030, "LON": 0.015,
        "TOK": 0.012, "PAR": 0.014, "BER": 0.016
    }
    
    # User behavior parameters
    USER_FRAUD_PROBABILITY: Dict[str, float] = {
        "new_user": 0.15,
        "returning_user": 0.01,
        "vip_user": 0.005
    }
    
    # Amount ranges by transaction type
    AMOUNT_RANGES: Dict[str, tuple] = {
        "retail": (10, 500),
        "wholesale": (100, 5000),
        "digital": (1, 100),
        "services": (50, 2000)
    }
    
    # Performance settings
    ENABLE_CACHING: bool = True
    CACHE_TTL: int = 300  # 5 minutes
    ENABLE_METRICS: bool = True

# Global configuration
CONFIG = FraudStreamConfig()

# ===============================================================================
# METRICS COLLECTION
# ===============================================================================

# Prometheus metrics
STREAM_EVENTS_TOTAL = Counter(
    'fraud_stream_events_total',
    'Total events generated in fraud stream',
    ['event_type', 'label']
)

STREAM_DURATION = Histogram(
    'fraud_stream_duration_seconds',
    'Fraud stream duration in seconds'
)

ACTIVE_STREAMS = Gauge(
    'fraud_stream_active_connections',
    'Number of active fraud stream connections'
)

FRAUD_RATE = Gauge(
    'fraud_stream_fraud_rate',
    'Current fraud detection rate'
)

THROUGHPUT_EVENTS_PER_SECOND = Gauge(
    'fraud_stream_throughput_events_per_second',
    'Current stream throughput in events/second'
)

# ===============================================================================
# DATA GENERATION ENGINE
# ===============================================================================

class FraudEventGenerator:
    """Generates realistic fraud detection events"""
    
    def __init__(self):
        self.event_counter = 0
        self.user_profiles = self._generate_user_profiles()
        self.device_pool = self._generate_device_pool()
        self.ip_ranges = self._generate_ip_ranges()
        
        # Time-based patterns
        self.hourly_patterns = {
            0: 0.3, 1: 0.2, 2: 0.15, 3: 0.1, 4: 0.1, 5: 0.15,
            6: 0.3, 7: 0.6, 8: 0.8, 9: 0.9, 10: 0.85, 11: 0.8,
            12: 0.75, 13: 0.8, 14: 0.85, 15: 0.9, 16: 0.95, 17: 1.0,
            18: 0.9, 19: 0.8, 20: 0.7, 21: 0.6, 22: 0.5, 23: 0.4
        }
    
    def _generate_user_profiles(self) -> Dict[int, Dict]:
        """Generate realistic user profiles"""
        profiles = {}
        for user_id in range(1000, 10000):
            profiles[user_id] = {
                "user_type": random.choices(
                    ["new_user", "returning_user", "vip_user"],
                    weights=[0.2, 0.75, 0.05]
                )[0],
                "avg_transaction": random.uniform(50, 500),
                "preferred_locations": random.sample(
                    list(CONFIG.LOCATION_FRAUD_RATES.keys()), 
                    random.randint(1, 3)
                ),
                "risk_score": random.uniform(0.1, 0.8)
            }
        return profiles
    
    def _generate_device_pool(self) -> List[str]:
        """Generate realistic device types"""
        return [
            "iOS", "Android", "Web-Chrome", "Web-Safari", 
            "Web-Firefox", "POS", "ATM", "Mobile-App"
        ]
    
    def _generate_ip_ranges(self) -> List[str]:
        """Generate realistic IP address ranges"""
        return [
            f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
            f"10.0.{random.randint(1,255)}.{random.randint(1,255)}",
            f"172.16.{random.randint(1,255)}.{random.randint(1,255)}"
        ]
    
    def calculate_fraud_probability(
        self, 
        user_id: int, 
        amount: float, 
        location: str,
        hour: int
    ) -> float:
        """Calculate realistic fraud probability"""
        
        user_profile = self.user_profiles.get(user_id, self.user_profiles[1000])
        base_prob = CONFIG.BASE_FRAUD_RATE
        
        # User-based probability
        user_prob = CONFIG.USER_FRAUD_PROBABILITY.get(
            user_profile["user_type"], 
            base_prob
        )
        
        # Amount-based probability
        if amount > 1000:
            amount_multiplier = 1.5
        elif amount > 500:
            amount_multiplier = 1.2
        else:
            amount_multiplier = 1.0
        
        # Location-based probability
        location_prob = CONFIG.LOCATION_FRAUD_RATES.get(location, base_prob)
        
        # Time-based pattern
        time_multiplier = self.hourly_patterns.get(hour, 1.0)
        
        # Combine probabilities
        combined_prob = (
            user_prob * 
            location_prob * 
            amount_multiplier * 
            time_multiplier
        )
        
        # Add some randomness
        noise = random.uniform(0.8, 1.2)
        
        return min(combined_prob * noise, 0.95)  # Cap at 95%
    
    def generate_event(self) -> FraudEvent:
        """Generate a single fraud detection event"""
        self.event_counter += 1
        
        # User selection
        user_id = random.randint(1000, 9999)
        user_profile = self.user_profiles.get(user_id, self.user_profiles[1000])
        
        # Location selection
        location = random.choice(
            user_profile["preferred_locations"] or 
            list(CONFIG.LOCATION_FRAUD_RATES.keys())
        )
        
        # Amount generation
        transaction_type = random.choice(list(CONFIG.AMOUNT_RANGES.keys()))
        amount_range = CONFIG.AMOUNT_RANGES[transaction_type]
        amount = round(random.uniform(*amount_range), 2)
        
        # Calculate fraud probability
        current_hour = datetime.utcnow().hour
        fraud_prob = self.calculate_fraud_probability(
            user_id, amount, location, current_hour
        )
        
        # Determine if fraud
        is_fraud = random.random() < fraud_prob
        
        # Generate risk score (correlated with fraud probability)
        if is_fraud:
            risk_score = random.uniform(0.7, 0.95)
        else:
            risk_score = random.uniform(0.1, 0.6)
        
        # Create event
        event = FraudEvent(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            amount=amount,
            location=location,
            device_type=random.choice(self.device_pool),
            payment_method=random.choice(["credit", "debit", "paypal", "crypto"]),
            ip_address=random.choice(self.ip_ranges),
            risk_score=round(risk_score, 3),
            label="fraud" if is_fraud else "legit",
            metadata={
                "transaction_type": transaction_type,
                "user_type": user_profile["user_type"],
                "hour_of_day": current_hour,
                "velocity_score": random.uniform(0.1, 1.0)
            }
        )
        
        # Update metrics
        if CONFIG.ENABLE_METRICS:
            STREAM_EVENTS_TOTAL.labels(
                event_type=transaction_type,
                label=event.label
            ).inc()
        
        return event

# Global event generator
event_generator = FraudEventGenerator()

# ===============================================================================
# STREAM MANAGER
# ===============================================================================

class StreamManager:
    """Manages active fraud detection streams"""
    
    def __init__(self):
        self.active_streams: Dict[str, StreamMetrics] = {}
        self.redis_client: Optional[redis.Redis] = None
        self._initialize_redis()
    
    async def _initialize_redis(self):
        """Initialize Redis client for caching"""
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Redis connected for stream caching")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
    
    def create_stream(self, stream_id: str) -> StreamMetrics:
        """Create a new stream metrics tracker"""
        metrics = StreamMetrics()
        self.active_streams[stream_id] = metrics
        ACTIVE_STREAMS.inc()
        return metrics
    
    def remove_stream(self, stream_id: str):
        """Remove stream and update metrics"""
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
            ACTIVE_STREAMS.dec()
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all streams"""
        total_events = sum(
            metrics.events_generated 
            for metrics in self.active_streams.values()
        )
        total_fraud = sum(
            metrics.fraud_events 
            for metrics in self.active_streams.values()
        )
        
        global_fraud_rate = total_fraud / max(total_events, 1)
        FRAUD_RATE.set(global_fraud_rate)
        
        return {
            "active_streams": len(self.active_streams),
            "total_events": total_events,
            "total_fraud": total_fraud,
            "fraud_rate": round(global_fraud_rate, 4),
            "uptime": time.time() - min(
                (m.start_time for m in self.active_streams.values()),
                default=time.time()
            )
        }

# Global stream manager
stream_manager = StreamManager()

# ===============================================================================
# STREAM ENDPOINTS
# ===============================================================================

@router.get(
    "/demo",
    response_model=Dict[str, Any],
    summary="Demo Fraud Detection",
    description="Returns a sample batch of fraud detection events",
    tags=["Demo"]
)
async def demo_fraud_detection(
    count: int = Query(10, ge=1, le=100, description="Number of events to generate"),
    include_fraud_only: bool = Query(False, description="Include only fraud events")
) -> Dict[str, Any]:
    """
    Generate demo fraud detection events for testing and preview.
    Returns a static batch of events with realistic fraud patterns.
    """
    start_time = time.time()
    
    try:
        events = []
        fraud_count = 0
        
        # Generate events
        while len(events) < count:
            event = event_generator.generate_event()
            
            if include_fraud_only and event.label != "fraud":
                continue
            
            events.append(event.to_dict())
            
            if event.label == "fraud":
                fraud_count += 1
        
        # Calculate metrics
        processing_time = (time.time() - start_time) * 1000
        fraud_rate = fraud_count / len(events)
        
        # Update metrics
        if CONFIG.ENABLE_METRICS:
            STREAM_DURATION.observe(processing_time / 1000)
        
        return {
            "demo": True,
            "events": events,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "event_count": len(events),
                "fraud_count": fraud_count,
                "fraud_rate": round(fraud_rate, 4),
                "processing_time_ms": round(processing_time, 2),
                "generator_version": "3.0.0"
            }
        }
        
    except Exception as e:
        logger.error(f"Demo endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate demo events")

@router.get(
    "/full",
    response_class=EventSourceResponse,
    summary="Real-Time Fraud Stream",
    description="Server-Sent Events stream of real-time fraud detection",
    tags=["Live Stream"]
)
async def full_fraud_stream(
    request: Request,
    batch_size: int = Query(10, ge=1, le=50, description="Events per batch"),
    interval_ms: int = Query(1, ge=1, le=100, description="Batch interval in milliseconds"),
    min_risk_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum risk score filter"),
    event_types: str = Query(None, description="Comma-separated event types to include")
) -> EventSourceResponse:
    """
    Real-time fraud detection stream using Server-Sent Events.
    Generates continuous stream of transaction events with fraud detection.
    """
    
    # Parse event types filter
    allowed_types = None
    if event_types:
        allowed_types = set(event.strip().lower() for event in event_types.split(','))
    
    # Create stream metrics
    stream_id = str(uuid.uuid4())
    metrics = stream_manager.create_stream(stream_id)
    
    async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming events"""
        
        try:
            logger.info(f"Starting fraud stream: {stream_id}")
            
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "stream_id": stream_id,
                    "connected_at": datetime.utcnow().isoformat() + "Z",
                    "config": {
                        "batch_size": batch_size,
                        "interval_ms": interval_ms,
                        "min_risk_score": min_risk_score
                    }
                })
            }
            
            # Main event loop
            batch_count = 0
            while True:
                batch_start = time.time()
                
                # Generate batch
                batch_events = []
                batch_fraud = 0
                batch_amount_total = 0.0
                
                for _ in range(batch_size):
                    event = event_generator.generate_event()
                    
                    # Apply filters
                    if event.risk_score < min_risk_score:
                        continue
                    
                    if allowed_types and event.metadata.get("transaction_type", "").lower() not in allowed_types:
                        continue
                    
                    batch_events.append(event.to_dict())
                    
                    if event.label == "fraud":
                        batch_fraud += 1
                    
                    batch_amount_total += event.amount
                
                # Update stream metrics
                metrics.events_generated += len(batch_events)
                metrics.fraud_events += batch_fraud
                metrics.legit_events += len(batch_events) - batch_fraud
                metrics.average_amount = (
                    (metrics.average_amount * (metrics.events_generated - len(batch_events)) + 
                     batch_amount_total) / metrics.events_generated
                    if metrics.events_generated > 0 else 0.0
                )
                
                # Calculate batch metrics
                batch_fraud_rate = batch_fraud / max(len(batch_events), 1)
                batch_avg_amount = batch_amount_total / max(len(batch_events), 1)
                processing_time = (time.time() - batch_start) * 1000
                throughput = len(batch_events) / max(processing_time / 1000, 1)
                
                # Send batch
                yield {
                    "event": "batch",
                    "data": json.dumps({
                        "batch_id": batch_count,
                        "stream_id": stream_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "events": batch_events,
                        "batch_metrics": {
                            "event_count": len(batch_events),
                            "fraud_count": batch_fraud,
                            "fraud_rate": round(batch_fraud_rate, 4),
                            "avg_amount": round(batch_avg_amount, 2),
                            "processing_time_ms": round(processing_time, 2),
                            "throughput_events_per_sec": round(throughput, 2)
                        },
                        "stream_metrics": {
                            "total_events": metrics.events_generated,
                            "total_fraud": metrics.fraud_events,
                            "overall_fraud_rate": round(
                                metrics.fraud_events / max(metrics.events_generated, 1), 4
                            ),
                            "uptime_seconds": round(time.time() - metrics.start_time, 2)
                        }
                    })
                }
                
                # Update global metrics
                if CONFIG.ENABLE_METRICS:
                    THROUGHPUT_EVENTS_PER_SECOND.set(throughput)
                
                batch_count += 1
                
                # Rate limiting
                await asyncio.sleep(interval_ms / 1000)
                
        except asyncio.CancelledError:
            logger.info(f"Stream cancelled: {stream_id}")
        except Exception as e:
            logger.error(f"Stream error: {stream_id} - {e}")
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": str(e),
                    "stream_id": stream_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
            }
        finally:
            # Cleanup
            stream_manager.remove_stream(stream_id)
            logger.info(f"Stream cleaned up: {stream_id}")
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

# ===============================================================================
# WEBSOCKET ENDPOINT (Alternative to SSE)
# ===============================================================================

@router.websocket("/ws/stream")
async def websocket_fraud_stream(websocket: WebSocket):
    """WebSocket alternative to Server-Sent Events"""
    
    await websocket.accept()
    stream_id = str(uuid.uuid4())
    metrics = stream_manager.create_stream(stream_id)
    
    try:
        logger.info(f"WebSocket connected: {stream_id}")
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "stream_id": stream_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        
        # Main streaming loop
        while True:
            # Generate events
            batch_events = []
            for _ in range(CONFIG.BATCH_SIZE):
                event = event_generator.generate_event()
                batch_events.append(event.to_dict())
                
                # Update metrics
                if event.label == "fraud":
                    metrics.fraud_events += 1
                else:
                    metrics.legit_events += 1
                
                metrics.events_generated += 1
            
            # Send batch
            await websocket.send_json({
                "type": "batch",
                "events": batch_events,
                "metrics": {
                    "total_events": metrics.events_generated,
                    "fraud_events": metrics.fraud_events,
                    "fraud_rate": metrics.fraud_events / max(metrics.events_generated, 1)
                }
            })
            
            await asyncio.sleep(CONFIG.BATCH_INTERVAL_MS / 1000)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {stream_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {stream_id} - {e}")
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
    finally:
        stream_manager.remove_stream(stream_id)

# ===============================================================================
# ANALYTICS ENDPOINTS
# ===============================================================================

@router.get(
    "/analytics",
    summary="Stream Analytics",
    description="Get analytics and statistics from fraud detection stream",
    tags=["Analytics"]
)
async def get_stream_analytics(
    time_window: int = Query(300, ge=60, le=3600, description="Time window in seconds")
) -> Dict[str, Any]:
    """Get real-time analytics from the fraud detection stream"""
    
    try:
        global_metrics = stream_manager.get_global_metrics()
        
        # Calculate time-based analytics
        current_time = datetime.utcnow()
        window_start = current_time - timedelta(seconds=time_window)
        
        # Generate sample analytics (in production, query actual data)
        analytics = {
            "time_window": time_window,
            "current_time": current_time.isoformat() + "Z",
            "window_start": window_start.isoformat() + "Z",
            "global_metrics": global_metrics,
            "fraud_patterns": {
                "by_location": self._analyze_fraud_by_location(),
                "by_amount_range": self._analyze_fraud_by_amount(),
                "by_hour": self._analyze_fraud_by_hour(),
                "by_device_type": self._analyze_fraud_by_device()
            },
            "performance": {
                "average_batch_size": CONFIG.BATCH_SIZE,
                "current_throughput": THROUGHPUT_EVENTS_PER_SECOND._value.get() or 0,
                "peak_throughput": 12000,  # Would be calculated from historical data
                "latency_ms": 1.2
            },
            "alerts": self._generate_fraud_alerts()
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"Analytics endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")

def _analyze_fraud_by_location(self) -> Dict[str, Any]:
    """Analyze fraud patterns by location"""
    location_stats = {}
    for location in CONFIG.LOCATION_FRAUD_RATES:
        fraud_rate = CONFIG.LOCATION_FRAUD_RATES[location]
        location_stats[location] = {
            "fraud_rate": fraud_rate,
            "risk_level": "high" if fraud_rate > 0.02 else "medium" if fraud_rate > 0.015 else "low"
        }
    return location_stats

def _analyze_fraud_by_amount(self) -> Dict[str, Any]:
    """Analyze fraud patterns by amount range"""
    return {
        "0-100": {"fraud_rate": 0.01, "count": 1000},
        "100-500": {"fraud_rate": 0.02, "count": 800},
        "500-1000": {"fraud_rate": 0.04, "count": 300},
        "1000+": {"fraud_rate": 0.08, "count": 150}
    }

def _analyze_fraud_by_hour(self) -> Dict[str, Any]:
    """Analyze fraud patterns by hour of day"""
    return {
        str(hour): {"fraud_rate": rate * 0.02, "activity_level": "high" if rate > 0.7 else "medium"}
        for hour, rate in event_generator.hourly_patterns.items()
    }

def _analyze_fraud_by_device(self) -> Dict[str, Any]:
    """Analyze fraud patterns by device type"""
    return {
        "iOS": {"fraud_rate": 0.015, "count": 400},
        "Android": {"fraud_rate": 0.025, "count": 350},
        "Web-Chrome": {"fraud_rate": 0.03, "count": 500},
        "POS": {"fraud_rate": 0.01, "count": 200}
    }

def _generate_fraud_alerts(self) -> List[Dict[str, Any]]:
    """Generate current fraud alerts"""
    return [
        {
            "alert_id": str(uuid.uuid4()),
            "type": "spike_detection",
            "severity": "medium",
            "message": "Unusual activity detected in NY region",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": {"location": "NY", "fraud_rate": 0.05}
        }
    ]

# ===============================================================================
# HEALTH CHECK ENDPOINT
# ===============================================================================

@router.get(
    "/health",
    summary="Health Check",
    description="Check fraud detection stream service health",
    tags=["Health"]
)
async def health_check() -> Dict[str, Any]:
    """Health check for fraud detection stream service"""
    
    try:
        # Generate test event to verify generator
        test_event = event_generator.generate_event()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "fraud_detection_stream",
            "version": "3.0.0",
            "configuration": {
                "batch_size": CONFIG.BATCH_SIZE,
                "base_fraud_rate": CONFIG.BASE_FRAUD_RATE,
                "max_concurrent_streams": CONFIG.MAX_CONCURRENT_STREAMS
            },
            "active_streams": len(stream_manager.active_streams),
            "test_event_generated": bool(test_event),
            "redis_connected": stream_manager.redis_client is not None
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
        )

# ===============================================================================
# UTILITY FUNCTIONS
# ===============================================================================

def create_sample_fraud_event() -> Dict[str, Any]:
    """Create a sample fraud event for testing"""
    event = event_generator.generate_event()
    return event.to_dict()

# Export for testing
__all__ = [
    "router",
    "FraudEvent",
    "StreamManager",
    "FraudEventGenerator",
    "create_sample_fraud_event"
]
