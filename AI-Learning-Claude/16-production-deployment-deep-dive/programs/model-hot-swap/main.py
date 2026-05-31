"""
Model Hot-Swap Simulator
=========================

Simulates hot-swapping AI models in production without downtime.
The challenge: replace a model that's actively serving requests without
dropping any in-flight requests or causing errors.

Key techniques demonstrated:
- Graceful drain: Stop sending NEW requests to old model, wait for in-flight to complete
- Pre-warm: Load new model and run warm-up inference before it receives traffic
- Atomic switch: Swap the serving pointer in one operation
- Connection draining with timeout
- Health validation of new model before swap
"""

import time
import random
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
from collections import deque


class ModelState(Enum):
    LOADING = "LOADING"
    WARMING_UP = "WARMING_UP"
    READY = "READY"
    SERVING = "SERVING"
    DRAINING = "DRAINING"
    UNLOADED = "UNLOADED"


@dataclass
class InFlightRequest:
    request_id: str
    start_time: float
    model_version: str


@dataclass
class ModelInstance:
    """Represents a loaded model instance in memory."""
    name: str
    version: str
    state: ModelState = ModelState.LOADING
    memory_mb: int = 2048
    load_time_sec: float = 2.0
    warmup_requests: int = 10
    in_flight: List[InFlightRequest] = field(default_factory=list)
    total_served: int = 0
    accuracy: float = 0.95
    latency_ms: float = 30.0

    def __str__(self):
        return f"{self.name} v{self.version} [{self.state.value}]"

    def serve_request(self, request_id: str) -> float:
        """Serve a request. Returns latency."""
        req = InFlightRequest(request_id, time.time(), self.version)
        self.in_flight.append(req)
        # Simulate processing
        latency = random.gauss(self.latency_ms, self.latency_ms * 0.1)
        time.sleep(latency / 5000)  # Scaled down for simulation
        self.in_flight.remove(req)
        self.total_served += 1
        return latency


class ModelServer:
    """
    Manages the lifecycle of model instances and handles hot-swapping.
    
    In production, this pattern is used by:
    - TensorFlow Serving (model versioning + graceful transitions)
    - NVIDIA Triton (model loading/unloading with zero downtime)
    - TorchServe (model archiver + management API)
    - Custom serving layers at large AI companies
    """

    def __init__(self):
        self.active_model: Optional[ModelInstance] = None
        self.pending_model: Optional[ModelInstance] = None
        self.request_counter = 0
        self.dropped_requests = 0
        self.swap_history: List[Dict] = []
        self._drain_timeout_sec = 5.0
        self._is_draining = False

    def load_model(self, model: ModelInstance) -> bool:
        """
        Load a model into memory. Simulates the time it takes to:
        - Read model weights from disk/object storage
        - Deserialize into framework (PyTorch, TF)
        - Move to GPU memory
        - Compile/optimize (TensorRT, ONNX Runtime)
        """
        print(f"    Loading {model}...")
        model.state = ModelState.LOADING

        # Simulate loading time (in production: 2-60 seconds depending on model size)
        steps = ["Reading weights from storage",
                 "Deserializing model graph",
                 "Allocating GPU memory",
                 "Optimizing compute graph"]
        for i, step in enumerate(steps):
            time.sleep(model.load_time_sec / len(steps))
            print(f"      [{i+1}/{len(steps)}] {step}...")

        model.state = ModelState.WARMING_UP
        print(f"    Model loaded into memory ({model.memory_mb}MB)")
        return True

    def warm_up_model(self, model: ModelInstance) -> bool:
        """
        Pre-warm the model by running inference on dummy/cached inputs.
        
        Why warm-up matters:
        - First inference is often 10-100x slower (JIT compilation, cache cold)
        - GPU kernels need to be compiled for specific input shapes
        - Memory allocators need to establish pools
        - Without warm-up, first real users see terrible latency
        """
        print(f"    Warming up {model} with {model.warmup_requests} requests...")
        model.state = ModelState.WARMING_UP

        latencies = []
        for i in range(model.warmup_requests):
            latency = model.serve_request(f"warmup-{i}")
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        print(f"    Warm-up complete. Avg latency: {avg_latency:.1f}ms")
        print(f"    (First request: {latencies[0]:.1f}ms, Last: {latencies[-1]:.1f}ms)")

        model.state = ModelState.READY
        return True

    def validate_model(self, model: ModelInstance) -> bool:
        """
        Run validation checks on the new model before it serves real traffic.
        Catches issues like corrupted weights, wrong input format, etc.
        """
        print(f"    Validating {model}...")
        checks = [
            ("Input shape compatibility", True),
            ("Output range check", True),
            ("Latency within SLA", model.latency_ms < 100),
            ("Memory within budget", model.memory_mb < 8192),
            ("Accuracy spot-check", model.accuracy > 0.8),
        ]
        all_passed = True
        for check_name, result in checks:
            icon = "✓" if result else "✗"
            print(f"      {icon} {check_name}")
            if not result:
                all_passed = False
        return all_passed

    def drain_active_model(self) -> bool:
        """
        Gracefully drain the active model:
        1. Stop accepting NEW requests on the old model
        2. Wait for all in-flight requests to complete
        3. Timeout if requests take too long (to bound downtime)
        
        This is the CRITICAL step that prevents request drops.
        """
        if not self.active_model:
            return True

        model = self.active_model
        print(f"\n    Draining {model}...")
        model.state = ModelState.DRAINING
        self._is_draining = True

        # Simulate in-flight requests completing
        in_flight_count = len(model.in_flight)
        if in_flight_count > 0:
            print(f"    Waiting for {in_flight_count} in-flight requests...")
            start = time.time()
            while model.in_flight and (time.time() - start) < self._drain_timeout_sec:
                time.sleep(0.1)
            remaining = len(model.in_flight)
            if remaining > 0:
                print(f"    ⚠ Drain timeout! {remaining} requests will be retried by client")
                self.dropped_requests += remaining
        else:
            print(f"    No in-flight requests, drain immediate")

        model.state = ModelState.UNLOADED
        self._is_draining = False
        print(f"    Drain complete. Model served {model.total_served} total requests.")
        return True

    def hot_swap(self, new_model: ModelInstance) -> bool:
        """
        Execute the full hot-swap sequence:
        1. Load new model (parallel with old serving)
        2. Warm up new model
        3. Validate new model
        4. Drain old model (stop new requests)
        5. Atomic switch
        6. Unload old model
        
        The key insight: steps 1-3 happen while the OLD model is still serving.
        Only step 4-5 causes a brief period where we need to buffer/retry requests.
        """
        print(f"\n{'='*60}")
        print(f"  HOT-SWAP: {self.active_model} -> {new_model}")
        print(f"{'='*60}")

        swap_start = time.time()
        old_model = self.active_model

        # Phase 1: Load new model (old model still serving)
        print(f"\n  Phase 1: LOAD (old model still serving traffic)")
        if not self.load_model(new_model):
            print("  ✗ Load failed, aborting swap")
            return False

        # Phase 2: Warm up (old model still serving)
        print(f"\n  Phase 2: WARM-UP (old model still serving traffic)")
        if not self.warm_up_model(new_model):
            print("  ✗ Warm-up failed, aborting swap")
            return False

        # Phase 3: Validate
        print(f"\n  Phase 3: VALIDATE")
        if not self.validate_model(new_model):
            print("  ✗ Validation failed, aborting swap")
            new_model.state = ModelState.UNLOADED
            return False

        # Phase 4: Drain old model
        print(f"\n  Phase 4: DRAIN old model")
        if old_model:
            self.drain_active_model()

        # Phase 5: Atomic switch
        print(f"\n  Phase 5: ATOMIC SWITCH")
        new_model.state = ModelState.SERVING
        self.active_model = new_model
        print(f"    Serving pointer updated: now serving {new_model}")
        print(f"    (In production: update routing table / service discovery)")

        # Phase 6: Cleanup
        print(f"\n  Phase 6: CLEANUP")
        if old_model:
            print(f"    Freeing {old_model.memory_mb}MB from old model")
            old_model.state = ModelState.UNLOADED

        swap_duration = time.time() - swap_start
        downtime_ms = 50  # Simulated: only the atomic switch causes "downtime"

        self.swap_history.append({
            "from": str(old_model) if old_model else "None",
            "to": str(new_model),
            "duration_sec": swap_duration,
            "downtime_ms": downtime_ms,
        })

        print(f"\n  ✓ HOT-SWAP COMPLETE")
        print(f"    Total swap time: {swap_duration:.2f}s")
        print(f"    Actual downtime: ~{downtime_ms}ms (only during atomic switch)")
        print(f"    Requests dropped: {self.dropped_requests}")
        return True

    def simulate_serving(self, num_requests: int):
        """Simulate serving production traffic."""
        if not self.active_model or self.active_model.state != ModelState.SERVING:
            print("    No active model to serve!")
            return

        print(f"\n    Serving {num_requests} requests with {self.active_model}...")
        latencies = []
        for i in range(num_requests):
            self.request_counter += 1
            lat = self.active_model.serve_request(f"prod-{self.request_counter}")
            latencies.append(lat)

        avg = sum(latencies) / len(latencies)
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        print(f"    Results: avg={avg:.1f}ms, p99={p99:.1f}ms, served={num_requests}")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          MODEL HOT-SWAP SIMULATOR                            ║
║          Zero-Downtime Model Replacement                     ║
╠══════════════════════════════════════════════════════════════╣
║  Pattern: Load new model alongside old, warm it up,          ║
║  drain old model gracefully, then atomic pointer swap.        ║
║  Result: Model updates with near-zero request drops.         ║
╚══════════════════════════════════════════════════════════════╝
""")

    server = ModelServer()

    # --- Initial deployment ---
    print("━" * 60)
    print("  SCENARIO 1: Initial model deployment")
    print("━" * 60)

    v1 = ModelInstance("recommendation-model", "1.0.0",
                       memory_mb=2048, load_time_sec=1.0,
                       warmup_requests=5, accuracy=0.92, latency_ms=25)

    server.load_model(v1)
    server.warm_up_model(v1)
    server.validate_model(v1)
    v1.state = ModelState.SERVING
    server.active_model = v1
    print(f"\n  ✓ Initial deployment complete: {v1}")
    server.simulate_serving(50)

    # --- Hot-swap to v2 ---
    print("\n" + "━" * 60)
    print("  SCENARIO 2: Hot-swap to improved model v2.0.0")
    print("━" * 60)
    print("  (Better accuracy, slightly more memory)")

    v2 = ModelInstance("recommendation-model", "2.0.0",
                       memory_mb=3072, load_time_sec=1.5,
                       warmup_requests=8, accuracy=0.96, latency_ms=22)
    server.hot_swap(v2)
    server.simulate_serving(50)

    # --- Hot-swap to v3 (larger model) ---
    print("\n" + "━" * 60)
    print("  SCENARIO 3: Hot-swap to large model v3.0.0")
    print("━" * 60)
    print("  (Much larger model, longer load time)")

    v3 = ModelInstance("recommendation-model", "3.0.0",
                       memory_mb=6144, load_time_sec=2.0,
                       warmup_requests=10, accuracy=0.97, latency_ms=35)
    server.hot_swap(v3)
    server.simulate_serving(50)

    # --- Failed swap (bad model) ---
    print("\n" + "━" * 60)
    print("  SCENARIO 4: Attempted swap with BAD model (should abort)")
    print("━" * 60)

    v4_bad = ModelInstance("recommendation-model", "4.0.0-beta",
                           memory_mb=2048, load_time_sec=0.8,
                           warmup_requests=5, accuracy=0.60, latency_ms=150)
    result = server.hot_swap(v4_bad)
    if not result:
        print(f"\n  The system correctly rejected the bad model!")
        print(f"  Still serving: {server.active_model}")
    server.simulate_serving(20)

    # --- Summary ---
    print(f"""
{'━'*60}
  SWAP HISTORY
{'━'*60}""")
    for i, swap in enumerate(server.swap_history, 1):
        print(f"  {i}. {swap['from']} -> {swap['to']}")
        print(f"     Duration: {swap['duration_sec']:.2f}s | Downtime: {swap['downtime_ms']}ms")

    print(f"""
{'━'*60}
  KEY TAKEAWAYS
{'━'*60}
  1. PARALLEL LOADING: New model loads while old one serves
     - Total swap time != downtime
     - Users only experience downtime during the atomic switch
     
  2. PRE-WARMING is critical for AI models:
     - First inference can be 10-100x slower
     - JIT compilation, CUDA kernel caching, memory pools
     - Always warm up before routing real traffic
     
  3. GRACEFUL DRAIN prevents request drops:
     - Stop new requests -> wait for in-flight -> switch
     - Timeout prevents unbounded drain time
     - Clients should implement retry logic for edge cases
     
  4. VALIDATION GATES catch bad models:
     - Check accuracy, latency, memory BEFORE swap
     - Abort and keep old model if validation fails
     - This is your last line of defense
     
  5. PRODUCTION IMPLEMENTATIONS:
     - TF Serving: --model_config_file with version policy
     - Triton: Model repository polling + load/unload API
     - TorchServe: Management API register/scale-worker
     - Custom: Shared-nothing architecture with health checks
     
  6. MEMORY PLANNING:
     - During swap, BOTH models are in memory simultaneously
     - Need headroom: old_model + new_model + overhead
     - GPU memory is the bottleneck, plan accordingly
{'━'*60}
""")


if __name__ == "__main__":
    main()
