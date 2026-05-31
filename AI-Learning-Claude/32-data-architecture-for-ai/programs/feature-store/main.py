"""
Feature Store Simulator for AI Systems
========================================
Demonstrates offline store, online store, feature registry,
training-serving consistency, and point-in-time correctness.

Run: python3 main.py
No dependencies required (standard library only).
"""

import time
import hashlib
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
import random


# =============================================================================
# FEATURE REGISTRY
# =============================================================================

class FeatureDefinition:
    """Defines a feature: its computation logic, owner, version, and metadata."""
    
    def __init__(self, name: str, description: str, owner: str,
                 version: str, dtype: str, computation: str,
                 freshness_sla: str, entity_key: str):
        self.name = name
        self.description = description
        self.owner = owner
        self.version = version
        self.dtype = dtype
        self.computation = computation
        self.freshness_sla = freshness_sla
        self.entity_key = entity_key
        self.created_at = datetime.now()
        self.consumers: List[str] = []
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "owner": self.owner,
            "dtype": self.dtype,
            "freshness_sla": self.freshness_sla,
            "consumers": self.consumers,
        }


class FeatureRegistry:
    """Central catalog of all features with versioning and metadata."""
    
    def __init__(self):
        self.features: Dict[str, FeatureDefinition] = {}
        self.versions: Dict[str, List[str]] = defaultdict(list)
    
    def register(self, feature: FeatureDefinition) -> None:
        key = f"{feature.name}:{feature.version}"
        self.features[key] = feature
        self.versions[feature.name].append(feature.version)
        print(f"  [Registry] Registered feature '{feature.name}' v{feature.version}")
    
    def get(self, name: str, version: Optional[str] = None) -> Optional[FeatureDefinition]:
        if version is None:
            version = self.versions[name][-1] if name in self.versions else None
        if version is None:
            return None
        return self.features.get(f"{name}:{version}")
    
    def list_features(self) -> List[Dict]:
        return [f.to_dict() for f in self.features.values()]
    
    def add_consumer(self, feature_name: str, consumer: str) -> None:
        for key, feat in self.features.items():
            if feat.name == feature_name:
                feat.consumers.append(consumer)


# =============================================================================
# OFFLINE STORE (Batch Features)
# =============================================================================

class OfflineStore:
    """
    Stores historical feature values for training.
    Supports point-in-time joins to prevent data leakage.
    """
    
    def __init__(self):
        # entity_key -> [(timestamp, feature_values)]
        self.store: Dict[str, List[Tuple[datetime, Dict[str, Any]]]] = defaultdict(list)
        self.write_count = 0
    
    def write_features(self, entity_key: str, features: Dict[str, Any],
                       timestamp: datetime) -> None:
        self.store[entity_key].append((timestamp, features.copy()))
        self.store[entity_key].sort(key=lambda x: x[0])
        self.write_count += 1
    
    def get_features_at_time(self, entity_key: str, 
                              as_of: datetime) -> Optional[Dict[str, Any]]:
        """Point-in-time correct feature retrieval."""
        if entity_key not in self.store:
            return None
        
        # Find the latest feature values BEFORE as_of timestamp
        result = None
        for ts, features in self.store[entity_key]:
            if ts <= as_of:
                result = features
            else:
                break
        return result
    
    def get_training_dataset(self, events: List[Dict]) -> List[Dict]:
        """
        Generate training dataset with point-in-time correct features.
        Each event gets features AS THEY EXISTED at event time.
        """
        training_data = []
        for event in events:
            entity_key = event["entity_key"]
            event_time = event["timestamp"]
            features = self.get_features_at_time(entity_key, event_time)
            if features:
                row = {**event, **features}
                training_data.append(row)
        return training_data


# =============================================================================
# ONLINE STORE (Low-Latency Serving)
# =============================================================================

class OnlineStore:
    """
    Stores latest feature values for real-time inference.
    Optimized for low-latency key-value lookups (simulates Redis/DynamoDB).
    """
    
    def __init__(self):
        # entity_key -> {feature_name: value}
        self.store: Dict[str, Dict[str, Any]] = {}
        self.last_updated: Dict[str, datetime] = {}
        self.read_latencies: List[float] = []
    
    def write_features(self, entity_key: str, features: Dict[str, Any]) -> None:
        if entity_key not in self.store:
            self.store[entity_key] = {}
        self.store[entity_key].update(features)
        self.last_updated[entity_key] = datetime.now()
    
    def get_features(self, entity_key: str, 
                      feature_names: List[str]) -> Dict[str, Any]:
        """Low-latency feature retrieval for serving."""
        start = time.time()
        
        result = {}
        if entity_key in self.store:
            for name in feature_names:
                result[name] = self.store[entity_key].get(name)
        
        # Simulate ~1ms latency
        latency_ms = (time.time() - start) * 1000 + random.uniform(0.5, 2.0)
        self.read_latencies.append(latency_ms)
        return result
    
    def get_staleness(self, entity_key: str) -> Optional[float]:
        if entity_key in self.last_updated:
            delta = datetime.now() - self.last_updated[entity_key]
            return delta.total_seconds()
        return None


# =============================================================================
# FEATURE COMPUTATION ENGINE
# =============================================================================

class FeatureComputeEngine:
    """Computes features from raw data (batch and streaming simulation)."""
    
    def __init__(self, offline_store: OfflineStore, online_store: OnlineStore):
        self.offline_store = offline_store
        self.online_store = online_store
    
    def compute_batch_features(self, raw_events: List[Dict]) -> Dict[str, Dict]:
        """
        Batch feature computation (simulates Spark job).
        Computes aggregate features over historical data.
        """
        print("\n  [Batch] Computing aggregate features...")
        
        # Group events by user
        user_events: Dict[str, List[Dict]] = defaultdict(list)
        for event in raw_events:
            user_events[event["user_id"]].append(event)
        
        features_computed = {}
        for user_id, events in user_events.items():
            features = {
                "total_interactions": len(events),
                "unique_documents": len(set(e.get("doc_id", "") for e in events)),
                "avg_session_duration_sec": sum(e.get("duration", 0) for e in events) / max(len(events), 1),
                "most_active_hour": max(range(24), key=lambda h: sum(1 for e in events if e.get("hour", 0) == h)),
                "feedback_ratio": sum(1 for e in events if e.get("feedback")) / max(len(events), 1),
            }
            
            # Write to both stores
            timestamp = max(e["timestamp"] for e in events)
            self.offline_store.write_features(user_id, features, timestamp)
            self.online_store.write_features(user_id, features)
            features_computed[user_id] = features
        
        print(f"  [Batch] Computed features for {len(features_computed)} users")
        return features_computed
    
    def compute_streaming_feature(self, event: Dict) -> Dict[str, Any]:
        """
        Streaming feature computation (simulates Flink/Kafka Streams).
        Updates features in real-time as events arrive.
        """
        user_id = event["user_id"]
        
        # Get current features and increment
        current = self.online_store.get_features(user_id, ["clicks_5min", "session_active"])
        
        new_features = {
            "clicks_5min": (current.get("clicks_5min") or 0) + 1,
            "session_active": True,
            "last_activity_ts": event["timestamp"].isoformat(),
            "last_document_viewed": event.get("doc_id", ""),
        }
        
        self.online_store.write_features(user_id, new_features)
        return new_features


# =============================================================================
# TRAINING-SERVING CONSISTENCY CHECKER
# =============================================================================

class ConsistencyChecker:
    """Verifies that training and serving use identical feature computations."""
    
    def __init__(self, offline_store: OfflineStore, online_store: OnlineStore):
        self.offline = offline_store
        self.online = online_store
    
    def check_consistency(self, entity_key: str, feature_names: List[str]) -> Dict:
        """Compare offline (training) and online (serving) feature values."""
        online_features = self.online.get_features(entity_key, feature_names)
        
        # Get latest from offline
        offline_features = None
        if entity_key in self.offline.store and self.offline.store[entity_key]:
            _, offline_features = self.offline.store[entity_key][-1]
        
        mismatches = []
        if offline_features:
            for name in feature_names:
                online_val = online_features.get(name)
                offline_val = offline_features.get(name)
                if online_val != offline_val:
                    mismatches.append({
                        "feature": name,
                        "online": online_val,
                        "offline": offline_val,
                    })
        
        return {
            "entity_key": entity_key,
            "consistent": len(mismatches) == 0,
            "mismatches": mismatches,
        }


# =============================================================================
# SIMULATION
# =============================================================================

def generate_raw_events(num_users: int = 5, events_per_user: int = 20) -> List[Dict]:
    """Generate simulated user interaction events."""
    events = []
    base_time = datetime.now() - timedelta(days=30)
    
    doc_ids = [f"doc_{i:03d}" for i in range(50)]
    
    for user_idx in range(num_users):
        user_id = f"user_{user_idx:03d}"
        for event_idx in range(events_per_user):
            timestamp = base_time + timedelta(
                days=random.uniform(0, 30),
                hours=random.uniform(0, 23),
            )
            events.append({
                "user_id": user_id,
                "doc_id": random.choice(doc_ids),
                "interaction_type": random.choice(["view", "click", "bookmark", "share"]),
                "duration": random.uniform(5, 300),
                "hour": timestamp.hour,
                "timestamp": timestamp,
                "feedback": random.random() > 0.7,
            })
    
    events.sort(key=lambda x: x["timestamp"])
    return events


def demo_point_in_time_correctness(offline_store: OfflineStore):
    """Demonstrate why point-in-time correctness matters."""
    print("\n" + "=" * 70)
    print("DEMO: Point-in-Time Correctness")
    print("=" * 70)
    
    user = "user_pit_demo"
    
    # Write features at different times
    t1 = datetime.now() - timedelta(days=10)
    t2 = datetime.now() - timedelta(days=5)
    t3 = datetime.now() - timedelta(days=1)
    
    offline_store.write_features(user, {"click_count": 10, "avg_duration": 45.0}, t1)
    offline_store.write_features(user, {"click_count": 25, "avg_duration": 52.0}, t2)
    offline_store.write_features(user, {"click_count": 50, "avg_duration": 60.0}, t3)
    
    # Training event happened at t2 - should get features from t1 (before event)
    event_time = t2 - timedelta(hours=1)  # Just before t2 features were computed
    
    features = offline_store.get_features_at_time(user, event_time)
    
    print(f"\n  Event occurred at: {event_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Features AS OF event time: {features}")
    print(f"  (click_count=10, NOT 25 or 50 — those are from the future!)")
    
    print(f"\n  WRONG approach (using latest features):")
    latest = offline_store.get_features_at_time(user, datetime.now())
    print(f"  Latest features: {latest}")
    print(f"  Using click_count=50 for training would be DATA LEAKAGE!")
    
    print(f"\n  Point-in-time correctness prevents the model from 'seeing the future'")
    print(f"  This is the #1 source of training-serving skew in production systems")


def main():
    print("=" * 70)
    print("FEATURE STORE SIMULATOR FOR AI SYSTEMS")
    print("=" * 70)
    
    # -------------------------------------------------------------------------
    # 1. Feature Registry
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 1: Feature Registry — Catalog of All Features")
    print("-" * 70)
    
    registry = FeatureRegistry()
    
    features_to_register = [
        FeatureDefinition(
            name="user_total_interactions",
            description="Total user interactions in last 30 days",
            owner="engagement-team",
            version="1.0",
            dtype="int",
            computation="COUNT(*) from interactions WHERE ts > NOW() - 30d",
            freshness_sla="daily",
            entity_key="user_id",
        ),
        FeatureDefinition(
            name="user_avg_session_duration",
            description="Average session duration in seconds",
            owner="engagement-team",
            version="1.0",
            dtype="float",
            computation="AVG(duration) from sessions WHERE ts > NOW() - 30d",
            freshness_sla="daily",
            entity_key="user_id",
        ),
        FeatureDefinition(
            name="user_clicks_5min",
            description="User click count in sliding 5-minute window",
            owner="engagement-team",
            version="1.0",
            dtype="int",
            computation="COUNT(*) from clicks WINDOW TUMBLING(5min)",
            freshness_sla="real-time (seconds)",
            entity_key="user_id",
        ),
        FeatureDefinition(
            name="user_feedback_ratio",
            description="Ratio of interactions with explicit feedback",
            owner="ai-quality-team",
            version="2.0",
            dtype="float",
            computation="COUNT(feedback=true) / COUNT(*) from interactions",
            freshness_sla="daily",
            entity_key="user_id",
        ),
    ]
    
    for feat in features_to_register:
        registry.register(feat)
    
    registry.add_consumer("user_total_interactions", "search-ranking-model")
    registry.add_consumer("user_total_interactions", "recommendation-model")
    registry.add_consumer("user_clicks_5min", "real-time-personalization")
    
    print(f"\n  Registry contains {len(registry.features)} feature definitions")
    print(f"  Feature 'user_total_interactions' consumed by: "
          f"{registry.get('user_total_interactions').consumers}")
    
    # -------------------------------------------------------------------------
    # 2. Batch Feature Computation
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 2: Offline Store — Batch Feature Computation")
    print("-" * 70)
    
    offline_store = OfflineStore()
    online_store = OnlineStore()
    compute_engine = FeatureComputeEngine(offline_store, online_store)
    
    # Generate raw events
    raw_events = generate_raw_events(num_users=5, events_per_user=20)
    print(f"\n  Generated {len(raw_events)} raw events for 5 users over 30 days")
    
    # Compute batch features
    batch_features = compute_engine.compute_batch_features(raw_events)
    
    print(f"\n  Sample features for user_000:")
    for k, v in batch_features.get("user_000", {}).items():
        print(f"    {k}: {v}")
    
    # -------------------------------------------------------------------------
    # 3. Online Store — Real-Time Features
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 3: Online Store — Real-Time Feature Serving")
    print("-" * 70)
    
    # Simulate streaming events
    print("\n  Simulating real-time events arriving...")
    streaming_events = [
        {"user_id": "user_000", "doc_id": "doc_042", "timestamp": datetime.now()},
        {"user_id": "user_000", "doc_id": "doc_015", "timestamp": datetime.now()},
        {"user_id": "user_001", "doc_id": "doc_003", "timestamp": datetime.now()},
    ]
    
    for event in streaming_events:
        result = compute_engine.compute_streaming_feature(event)
        print(f"  [Stream] {event['user_id']} → clicks_5min={result['clicks_5min']}")
    
    # Demonstrate low-latency serving
    print(f"\n  Serving features for inference request:")
    features_needed = ["total_interactions", "unique_documents", "clicks_5min", "session_active"]
    served = online_store.get_features("user_000", features_needed)
    print(f"  user_000 features: {served}")
    
    if online_store.read_latencies:
        avg_latency = sum(online_store.read_latencies) / len(online_store.read_latencies)
        print(f"  Average serving latency: {avg_latency:.2f}ms (target: <10ms)")
    
    # -------------------------------------------------------------------------
    # 4. Training-Serving Consistency
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 4: Training-Serving Consistency Check")
    print("-" * 70)
    
    checker = ConsistencyChecker(offline_store, online_store)
    
    batch_feature_names = ["total_interactions", "unique_documents", 
                           "avg_session_duration_sec", "feedback_ratio"]
    
    for user_id in ["user_000", "user_001", "user_002"]:
        result = checker.check_consistency(user_id, batch_feature_names)
        status = "CONSISTENT" if result["consistent"] else "SKEW DETECTED"
        print(f"  {user_id}: {status}")
        if result["mismatches"]:
            for m in result["mismatches"]:
                print(f"    ⚠ {m['feature']}: online={m['online']}, offline={m['offline']}")
    
    print(f"\n  Note: Batch features are consistent (same computation writes to both stores)")
    print(f"  Streaming features (clicks_5min) are online-only — expected difference")
    
    # -------------------------------------------------------------------------
    # 5. Point-in-Time Correctness
    # -------------------------------------------------------------------------
    demo_point_in_time_correctness(offline_store)
    
    # -------------------------------------------------------------------------
    # 6. Training Dataset Generation
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("STEP 5: Training Dataset with Point-in-Time Features")
    print("-" * 70)
    
    # Create training events (prediction targets)
    training_events = [
        {"entity_key": "user_000", "timestamp": datetime.now() - timedelta(days=2), "label": 1},
        {"entity_key": "user_001", "timestamp": datetime.now() - timedelta(days=5), "label": 0},
        {"entity_key": "user_002", "timestamp": datetime.now() - timedelta(days=1), "label": 1},
    ]
    
    training_dataset = offline_store.get_training_dataset(training_events)
    
    print(f"\n  Training dataset: {len(training_dataset)} rows")
    print(f"  Each row has features AS OF the event time (no data leakage)")
    for row in training_dataset[:2]:
        entity = row.get("entity_key", "?")
        label = row.get("label", "?")
        interactions = row.get("total_interactions", "?")
        print(f"    {entity}: label={label}, total_interactions={interactions}")
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("FEATURE STORE SUMMARY")
    print("=" * 70)
    print(f"""
  Components demonstrated:
  ├── Feature Registry: {len(registry.features)} features cataloged with versions
  ├── Offline Store: {offline_store.write_count} feature writes (historical)
  ├── Online Store: {len(online_store.store)} entities with latest features
  ├── Batch Computation: Aggregate features from {len(raw_events)} events
  ├── Streaming Computation: Real-time features updated per event
  ├── Consistency Check: Training-serving skew detection
  └── Point-in-Time: Data leakage prevention for training

  Key architectural decisions:
  1. Same computation writes to BOTH offline and online stores
  2. Point-in-time joins prevent future data from leaking into training
  3. Feature registry enables discovery and prevents duplication
  4. Online store optimized for <10ms reads (serving)
  5. Offline store retains full history (training, debugging, compliance)
""")


if __name__ == "__main__":
    random.seed(42)
    main()
