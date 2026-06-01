# Phi (φ) Accrual Failure Detector

## 1. Problem Statement

In distributed systems, determining whether a remote node is alive or dead is fundamentally impossible to solve with certainty (FLP impossibility). Traditional failure detectors use a binary model — a node is either "alive" or "dead" — decided by a fixed timeout. This crude approach fails catastrophically in real-world environments where:

- **Network latency is variable** — packets traverse different paths, encounter congestion, get retransmitted
- **GC pauses** — JVM stop-the-world pauses can last hundreds of milliseconds to seconds
- **CPU saturation** — a node under heavy load delays heartbeat responses
- **Virtualization jitter** — hypervisor scheduling introduces unpredictable delays
- **Geographic distribution** — cross-datacenter links have fundamentally different latency profiles

The Phi Accrual Failure Detector (Hayashibara et al., 2004) replaces the binary alive/dead decision with a **continuous suspicion level φ** that grows over time since the last heartbeat, adapting to observed network behavior. The application layer chooses its own conviction threshold, decoupling detection mechanics from application-specific failure semantics.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    THE FUNDAMENTAL PROBLEM                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Binary Detector:     ALIVE ──────────── timeout ──→ DEAD           │
│                       (no middle ground, no nuance)                  │
│                                                                     │
│  Phi Accrual:         ALIVE ──→ slightly suspicious ──→ very        │
│                              suspicious ──→ probably dead ──→ dead   │
│                       (continuous confidence level)                  │
│                                                                     │
│  Reality:             Node might be: slow, overloaded, pausing,     │
│                       network-partitioned, actually crashed,         │
│                       restarting, or perfectly fine but delayed      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Traditional Failure Detection Limitations

### 2.1 Fixed Timeout Detector

The simplest failure detector: if no heartbeat arrives within T milliseconds, declare the node dead.

```
        Timeout T = 5 seconds
        
Timeline: ─────────────────────────────────────────────────────────→ time
              │         │         │              │
Heartbeats:   ♥         ♥         ♥              ♥
              t=0       t=2s      t=4s           t=11s
                                       │
                                       ├── 5s timeout ──┤
                                       │                │
                                       │         DECLARED DEAD! (at t=9s)
                                       │
                                       But node was actually alive...
                                       just had a 7-second GC pause
```

**The Dilemma:**

```
┌──────────────────────────────────────────────────────────────────────┐
│                     FIXED TIMEOUT DILEMMA                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Timeout too SHORT (e.g., 1s):                                       │
│  ┌─────────────────────────────────────────────┐                     │
│  │ ♥ ♥ ♥ ♥   (GC pause 1.2s)   ♥ ♥ ♥         │                     │
│  │         └── FALSE POSITIVE! Node removed    │                     │
│  │             from cluster, data re-replicated│                     │
│  │             unnecessary load spike          │                     │
│  └─────────────────────────────────────────────┘                     │
│  Result: Flapping, cascading failures, split-brain                   │
│                                                                      │
│  Timeout too LONG (e.g., 30s):                                       │
│  ┌─────────────────────────────────────────────┐                     │
│  │ ♥ ♥ ♥ ♥ X (node crashes)                   │                     │
│  │           └──── 30 seconds of silence ────┤ │                     │
│  │                                    Finally! │                     │
│  │                                    Dead.    │                     │
│  └─────────────────────────────────────────────┘                     │
│  Result: 30s of requests sent to dead node,                          │
│          30s of unavailability for that partition                     │
│                                                                      │
│  NO SINGLE TIMEOUT VALUE WORKS FOR ALL CONDITIONS                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Heartbeat-Based Detection (Doesn't Account for Variance)

```
    Network latency distribution (bimodal in practice):
    
    Frequency
    │
    │   ██
    │   ██ █                              
    │  ███ ██                         █   ← occasional slow packets
    │  ███ ███                       ██      (cross-rack, retransmits)
    │ ████ ████                     ████  
    │ █████████                    ██████  
    │███████████                  ████████ 
    ├───────────────────────────────────────→ latency (ms)
    0    50   100   150   200   250   300   350
    
    Fixed timeout at 200ms:
    - Catches 95% of heartbeats ✓
    - But that 5% tail causes false positives every few minutes ✗
    - In a 1000-node cluster: ~50 false positives per minute!
```

### 2.3 GC Pause Causing False Positive (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GC PAUSE FALSE POSITIVE SCENARIO                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Node A (monitor)          Network           Node B (monitored)         │
│  ─────────────────         ───────           ──────────────────         │
│        │                      │                     │                    │
│        │──── heartbeat req ───────────────────────→ │  t=0s             │
│        │                      │                     │                    │
│        │ ←── heartbeat resp ────────────────────────│  t=50ms           │
│        │                      │                     │                    │
│        │──── heartbeat req ───────────────────────→ │  t=1.0s           │
│        │                      │                     │                    │
│        │ ←── heartbeat resp ────────────────────────│  t=1.05s          │
│        │                      │                     │                    │
│        │──── heartbeat req ───────────────────────→ │  t=2.0s           │
│        │                      │                     │  ┌──────────────┐ │
│        │                      │                     │  │ STOP-THE-    │ │
│        │                      │                     │  │ WORLD GC     │ │
│        │      (waiting...)    │                     │  │ Major GC     │ │
│        │                      │                     │  │ compaction   │ │
│        │                      │                     │  │ 3.5 seconds  │ │
│        │   TIMEOUT=3s!        │                     │  │              │ │
│   ┌────┴────┐                 │                     │  │              │ │
│   │ DECLARE │  t=5.0s         │                     │  │              │ │
│   │  DEAD!  │                 │                     │  └──────────────┘ │
│   └────┬────┘                 │                     │                    │
│        │                      │                     │  (GC done, t=5.5s)│
│        │ ←── heartbeat resp ────────────────────────│  t=5.55s          │
│        │                      │                     │                    │
│   But we already evicted      │                     │  Node B is fine!  │
│   Node B from the cluster!    │                     │  But now orphaned │
│                               │                     │                    │
│   CONSEQUENCES:                                                         │
│   • Data re-replicated unnecessarily (network/disk I/O storm)           │
│   • Client connections to B dropped                                     │
│   • When B "comes back", split-brain possible                           │
│   • Cluster instability cascade if multiple nodes GC simultaneously     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phi (φ) Accrual Failure Detector Concept

### 3.1 Core Idea

Instead of outputting a boolean decision, the detector outputs a **suspicion level φ** (phi) on a continuous scale from 0 to ∞:

- **φ = 0**: No suspicion. Heartbeat just arrived.
- **φ = 1**: Mild suspicion. ~10% probability the node has crashed.
- **φ = 3**: Moderate suspicion. ~99.9% probability of failure.
- **φ = 8**: Near certainty. ~99.999999% probability of failure.
- **φ → ∞**: Absolute certainty (never actually reached).

The **application** sets its own threshold based on its tolerance for false positives vs detection speed:

```
┌──────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE SEPARATION                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              APPLICATION LAYER                           │     │
│  │                                                         │     │
│  │  "I need fast detection    "I need zero false positives │     │
│  │   (video streaming)"        (bank transactions)"        │     │
│  │         │                            │                  │     │
│  │    threshold = 3              threshold = 12            │     │
│  └─────────┼────────────────────────────┼──────────────────┘     │
│            │                            │                        │
│  ┌─────────▼────────────────────────────▼──────────────────┐     │
│  │              PHI ACCRUAL DETECTOR                        │     │
│  │                                                         │     │
│  │  Outputs: φ = 4.7 (current suspicion level)             │     │
│  │                                                         │     │
│  │  App 1 says: φ=4.7 > 3 → NODE IS DEAD (fast reaction)  │     │
│  │  App 2 says: φ=4.7 < 12 → NODE IS ALIVE (conservative) │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  SAME DETECTOR, DIFFERENT INTERPRETATIONS                        │
│  No reconfiguration needed for different use cases               │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 φ Value Progression Over Time

```
    φ (suspicion level)
    │
 12 ┤                                                          ╱
    │                                                        ╱
 10 ┤                                                      ╱
    │                                                    ╱    ← Cassandra
  8 ┤─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─╱─ ─ ─  threshold=8
    │                                                ╱
  6 ┤                                              ╱
    │                                            ╱
  4 ┤                                          ╱
    │                                        ╱
  3 ┤─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╱─ ─ ─ ─ ─ ─ ─ ─  aggressive
    │                                    ╱                     threshold=3
  2 ┤                                  ╱
    │                                ╱
  1 ┤                             ╱
    │                          ╱
  0 ┼─♥────♥────♥────♥───────────────────────────────────────→ time
    t=0   t=1s  t=2s  t=3s  t=4s  t=5s  t=6s  t=7s  t=8s
                             │
                     Last heartbeat received
                     (expected interval ~1s)
    
    After last heartbeat at t=3s:
    - t=4s: φ ≈ 0.5  (1s late, normal variance)
    - t=5s: φ ≈ 2.1  (2s late, getting suspicious)
    - t=6s: φ ≈ 4.8  (3s late, quite suspicious)
    - t=7s: φ ≈ 8.2  (4s late, Cassandra would convict)
    - t=8s: φ ≈ 12.1 (5s late, certainly dead)
```

### 3.3 Self-Adapting Behavior

```
    SCENARIO: Network conditions change mid-operation
    
    Phase 1: Fast, stable network (μ=50ms, σ=5ms)
    ───────────────────────────────────────────────
    ♥   ♥   ♥   ♥   ♥   ♥   ♥   ♥   ♥   ♥
    48  52  49  51  50  53  48  50  52  49  (inter-arrival ms)
    
    Detector learns: "Normal is ~50ms ± 5ms"
    → φ rises quickly if heartbeat is >70ms late
    
    Phase 2: Network degrades (μ=200ms, σ=40ms)  
    ───────────────────────────────────────────────
    ♥       ♥        ♥      ♥        ♥       ♥
    180    220      195    240      185     210    (inter-arrival ms)
    
    Detector adapts: "Normal is now ~200ms ± 40ms"
    → φ rises slowly, tolerates up to ~320ms without suspicion
    
    NO MANUAL RECONFIGURATION NEEDED!
    Fixed timeout would need operator intervention.
```

---

## 4. Algorithm in Detail

### 4.1 Mathematical Foundation

The algorithm maintains a **sliding window** of heartbeat inter-arrival times and uses statistical analysis to compute suspicion:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         ALGORITHM STEPS                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. COLLECT: Record inter-arrival times in sliding window            │
│     Window W = [t₁, t₂, t₃, ..., tₙ]                               │
│     where tᵢ = time between heartbeat i-1 and heartbeat i           │
│                                                                      │
│  2. COMPUTE STATISTICS:                                              │
│     μ = mean(W)        = (1/n) × Σ tᵢ                               │
│     σ² = variance(W)   = (1/n) × Σ (tᵢ - μ)²                       │
│     σ = std_dev(W)     = √σ²                                        │
│                                                                      │
│  3. ON QUERY "is node alive?":                                       │
│     t_now = current_time                                             │
│     t_last = time of last heartbeat received                         │
│     Δt = t_now - t_last   (time since last heartbeat)                │
│                                                                      │
│  4. COMPUTE PHI:                                                     │
│     P_later(Δt) = 1 - F(Δt | μ, σ²)                                 │
│                 = probability that a heartbeat would arrive           │
│                   LATER than Δt given the observed distribution       │
│                                                                      │
│     φ = -log₁₀(P_later(Δt))                                         │
│                                                                      │
│  5. INTERPRETATION:                                                  │
│     If P_later = 0.1 (10% chance still coming) → φ = 1              │
│     If P_later = 0.01 (1% chance) → φ = 2                           │
│     If P_later = 0.001 (0.1% chance) → φ = 3                        │
│     If P_later = 10⁻⁸ → φ = 8                                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 The CDF and Phi Calculation

Assuming inter-arrival times follow a **normal distribution** N(μ, σ²):

```
    F(x) = CDF of Normal Distribution
    
    Probability
    1.0 ┤                                    ─────────────────────
        │                                ╱
    0.9 ┤                              ╱
        │                            ╱
    0.8 ┤                          ╱
        │                        ╱
    0.7 ┤                      ╱
        │                    ╱
    0.5 ┤──────────────────╱───── ← F(μ) = 0.5 (at the mean)
        │                ╱
    0.3 ┤              ╱
        │            ╱
    0.2 ┤          ╱
        │        ╱
    0.1 ┤      ╱
        │    ╱
    0.0 ┤──╱──────────────────────────────────────────────────────
        └───┬──────┬──────┬──────┬──────┬──────┬──────┬──────────→
           μ-3σ  μ-2σ   μ-σ    μ    μ+σ   μ+2σ  μ+3σ        Δt
    
    
    P_later(Δt) = 1 - F(Δt)     (survival function / complementary CDF)
    
    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   φ = -log₁₀(P_later(Δt))                          │
    │     = -log₁₀(1 - F(Δt))                            │
    │                                                     │
    │   Example: μ = 1000ms, σ = 100ms                    │
    │                                                     │
    │   Δt = 1000ms: P_later = 0.5      → φ = 0.30       │
    │   Δt = 1100ms: P_later = 0.159    → φ = 0.80       │
    │   Δt = 1200ms: P_later = 0.0228   → φ = 1.64       │
    │   Δt = 1300ms: P_later = 0.00135  → φ = 2.87       │
    │   Δt = 1500ms: P_later = 2.87e-7  → φ = 6.54       │
    │   Δt = 1800ms: P_later = 1.3e-16  → φ = 15.9       │
    │                                                     │
    └─────────────────────────────────────────────────────┘
```

### 4.3 Exponential Growth of Suspicion

```
    φ value vs time since last heartbeat (μ=1000ms, σ=100ms)
    
    φ
    │
 16 ┤                                                    •
    │                                                   •
 14 ┤                                                  •
    │                                                 •
 12 ┤                                                •
    │                                               •
 10 ┤                                             •
    │                                            •
  8 ┤─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ •─ ─ ─ Cassandra threshold
    │                                        •
  6 ┤                                      •
    │                                    •
  4 ┤                                 •
    │                              •
  2 ┤                          •
    │                     • 
  1 ┤                •
    │          •
  0 ┤ •  •
    └──┬────┬────┬────┬────┬────┬────┬────┬────┬────→ Δt (ms)
      800 900 1000 1100 1200 1300 1400 1500 1600 1800
           │         │
           │    Expected (μ)
        Arrived early
        (φ stays near 0)
    
    KEY INSIGHT: φ grows SLOWLY near μ (tolerant of normal jitter)
                 φ grows FAST beyond μ+2σ (rapidly escalating suspicion)
                 This is the "accrual" — suspicion accumulates over time
```

### 4.4 Comparison: Normal vs Exponential Distribution

The original paper uses an **exponential distribution** for simplicity, while some implementations (like Akka) use a **normal distribution** for better fit:

```
    Exponential Distribution (λ = 1/μ):
    ────────────────────────────────────
    P_later(Δt) = e^(-λ × Δt)
    φ = -log₁₀(e^(-Δt/μ))
      = (Δt/μ) × log₁₀(e)
      = (Δt/μ) × 0.4343
    
    → φ grows LINEARLY with time! (simpler but less accurate)
    
    Normal Distribution N(μ, σ²):
    ─────────────────────────────
    P_later(Δt) = 1 - Φ((Δt - μ)/σ)    [Φ = standard normal CDF]
    φ = -log₁₀(1 - Φ((Δt - μ)/σ))
    
    → φ grows QUADRATICALLY in the tail (more aggressive, better fit)
    
    ┌──────────────────────────────────────────────┐
    │  φ growth comparison:                        │
    │                                              │
    │   φ    Exponential    Normal (σ=μ/10)        │
    │   ──   ───────────    ───────────────        │
    │   1    at Δt=2.3μ    at Δt≈μ+1.3σ           │
    │   3    at Δt=6.9μ    at Δt≈μ+3.1σ           │
    │   8    at Δt=18.4μ   at Δt≈μ+5.6σ           │
    │                                              │
    │  Normal detects failures MUCH faster         │
    │  because tail probability drops rapidly      │
    └──────────────────────────────────────────────┘
```

---

## 5. Sampling Window

### 5.1 Sliding Window Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SLIDING WINDOW (Ring Buffer)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Window Size = 1000 (configurable)                                  │
│                                                                     │
│  ┌────┬────┬────┬────┬────┬────┬────┬────┬─────┬────┐              │
│  │ 52 │ 48 │ 51 │ 55 │ 49 │ 53 │ 47 │ 50 │ ... │ 51 │ (ms)       │
│  └────┴────┴────┴────┴────┴────┴────┴────┴─────┴────┘              │
│    ↑                                              ↑                  │
│    oldest                                    newest (write pointer)   │
│                                                                     │
│  On new heartbeat:                                                  │
│    1. Compute inter-arrival: Δ = t_current - t_last_heartbeat       │
│    2. Insert Δ at write pointer                                     │
│    3. Advance write pointer (wraps around)                          │
│    4. Update running mean and variance (incremental)                │
│                                                                     │
│  Incremental statistics (Welford's algorithm):                      │
│    n += 1                                                           │
│    delta = new_value - mean                                         │
│    mean += delta / n                                                │
│    delta2 = new_value - mean                                        │
│    M2 += delta * delta2                                             │
│    variance = M2 / n                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Bootstrap Phase

When a node first starts monitoring another, it has no samples:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BOOTSTRAP STRATEGY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: No samples yet (0 heartbeats received)                │
│  ─────────────────────────────────────────────────              │
│  Use conservative defaults:                                     │
│    μ_initial = expected_heartbeat_interval (e.g., 1000ms)       │
│    σ_initial = μ_initial / 4 (e.g., 250ms)                     │
│  This prevents premature conviction of slow-starting nodes      │
│                                                                 │
│  Phase 2: Few samples (1-10 heartbeats)                         │
│  ─────────────────────────────────────────                      │
│  Blend initial estimates with observed data:                    │
│    μ = (μ_initial × (10-n) + μ_observed × n) / 10              │
│  High uncertainty → detector is conservative                    │
│                                                                 │
│  Phase 3: Sufficient samples (>10 heartbeats)                   │
│  ─────────────────────────────────────────────                  │
│  Use purely observed statistics                                 │
│  Detector is now calibrated for this specific link              │
│                                                                 │
│  Timeline:                                                      │
│  ─────────────────────────────────────────────────────→         │
│  │← conservative →│← blending →│← fully calibrated →│          │
│  0                 1            10                    ∞ samples  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Handling Outliers and Jitter

```
    Real-world inter-arrival time distribution:

    Count
    │
    │        █
    │       ███
    │      █████
    │     ███████
    │    █████████                          █  ← outliers (GC pause,
    │   ███████████                        ██    network retransmit)
    │  █████████████         █            ███
    │ ███████████████       ███          █████
    │████████████████████████████████████████████
    └────────────────────────────────────────────→ inter-arrival (ms)
    40  60  80  100  120  140  160  ...  400  500
    
    Strategies for robustness:
    ┌─────────────────────────────────────────────────────────┐
    │ 1. Large window size: outliers are diluted              │
    │    1 outlier in 1000 samples barely moves μ or σ        │
    │                                                         │
    │ 2. Minimum σ floor: prevent σ from being too small      │
    │    If network is very stable (σ→0), a tiny delay        │
    │    would cause φ to spike. Floor prevents this.         │
    │    min_std_deviation = 100ms (typical Akka default)     │
    │                                                         │
    │ 3. Maximum sample value cap (optional):                 │
    │    Discard inter-arrival times > 10×μ                   │
    │    These represent monitoring gaps, not real latency    │
    │                                                         │
    │ 4. Exponential moving average (alternative to window):  │
    │    μ_new = α × sample + (1-α) × μ_old                  │
    │    Gives more weight to recent samples                  │
    └─────────────────────────────────────────────────────────┘
```

---

## 6. Threshold Selection

### 6.1 φ Threshold vs False Positive Rate

```
┌────────────┬──────────────────────┬─────────────────┬────────────────────┐
│  φ thresh  │  P(false positive)   │  Detection time │  Use case          │
│            │  per check           │  (if μ=1s,σ=.1s)│                    │
├────────────┼──────────────────────┼─────────────────┼────────────────────┤
│     1      │  10%                 │  ~1.13s         │  Never use this    │
│     2      │  1%                  │  ~1.23s         │  Very aggressive   │
│     3      │  0.1%               │  ~1.31s         │  Fast detection    │
│     4      │  0.01%              │  ~1.37s         │  Moderate          │
│     5      │  0.001%             │  ~1.43s         │  Conservative      │
│     8      │  0.00000001%        │  ~1.56s         │  Cassandra default │
│    10      │  10⁻¹⁰              │  ~1.63s         │  Very conservative │
│    12      │  10⁻¹²              │  ~1.70s         │  Ultra-safe        │
│    16      │  10⁻¹⁶              │  ~1.84s         │  Paranoid          │
└────────────┴──────────────────────┴─────────────────┴────────────────────┘

Note: Detection time = time from actual crash until φ exceeds threshold
      Assumes last heartbeat arrived at expected time

KEY INSIGHT: Going from φ=3 to φ=8 only adds ~250ms detection delay
             but reduces false positives by 5 ORDERS OF MAGNITUDE.
             This is why Cassandra uses φ=8 — minimal latency cost,
             massive reliability gain.
```

### 6.2 Visual: Threshold Trade-off

```
    False Positive Rate (log scale)
    │
    │ •  φ=1
 -1 ┤
    │
 -2 ┤    •  φ=2
    │
 -3 ┤       •  φ=3
    │
 -4 ┤          •  φ=4
    │
 -5 ┤             •  φ=5
    │
 -6 ┤
    │
 -7 ┤
    │
 -8 ┤                       •  φ=8 (Cassandra)
    │
    └──────┬──────┬──────┬──────┬──────┬────→ Detection delay (ms)
          100    200    300    400    500     (added beyond μ)
    
    Sweet spot: φ = 5-8 for most production systems
    "Knee of the curve" — diminishing returns beyond φ=8
```

---

## 7. Advantages over Binary Detectors

```
┌─────────────────────────────────────────────────────────────────────────┐
│              COMPARISON: PHI ACCRUAL vs FIXED TIMEOUT                    │
├────────────────────────┬────────────────────────┬───────────────────────┤
│  Dimension             │  Fixed Timeout         │  Phi Accrual          │
├────────────────────────┼────────────────────────┼───────────────────────┤
│  Output                │  Boolean (alive/dead)  │  Continuous φ ∈ [0,∞) │
│  Adaptation            │  None (manual tuning)  │  Self-adapting        │
│  Network changes       │  Requires reconfig     │  Automatic            │
│  Multiple consumers    │  One threshold for all │  Each picks own       │
│  GC pause tolerance    │  Poor                  │  Excellent            │
│  Cross-DC deployment   │  Different configs     │  Single config        │
│  False positive rate   │  Unpredictable         │  Mathematically bound │
│  Tuning effort         │  High (per-env)        │  Low (set once)       │
│  Cold start            │  Works immediately     │  Needs bootstrap      │
│  Complexity            │  Trivial               │  Moderate             │
│  Memory overhead       │  O(1)                  │  O(window_size)       │
│  CPU overhead          │  O(1)                  │  O(1) amortized       │
└────────────────────────┴────────────────────────┴───────────────────────┘
```

**Key advantage: Separation of concerns**
- The detector outputs "how suspicious" (objective measurement)
- The application decides "how suspicious is too suspicious" (policy decision)
- Different services can have different tolerances without changing the detector

---

## 8. Real-World Implementations

### 8.1 Apache Cassandra

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CASSANDRA FAILURE DETECTION                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Configuration (cassandra.yaml):                                    │
│  ─────────────────────────────────                                  │
│    phi_convict_threshold: 8           # Default threshold           │
│                                                                     │
│  Implementation details:                                            │
│  ───────────────────────                                            │
│  • Class: org.apache.cassandra.gms.FailureDetector                  │
│  • Gossip-based heartbeats (GossipDigestSyn/Ack/Ack2)              │
│  • Window size: 1000 samples (ArrivalWindow)                        │
│  • Uses exponential distribution (not normal)                       │
│  • Heartbeat interval: 1 second (default)                           │
│  • Reports φ per-node via JMX                                       │
│                                                                     │
│  Gossip Protocol Integration:                                       │
│  ┌──────────┐    Gossip     ┌──────────┐                            │
│  │  Node A  │◄────────────► │  Node B  │                            │
│  │          │   (1/sec)     │          │                            │
│  │ ┌──────┐ │               │ ┌──────┐ │                            │
│  │ │ φ(B) │ │               │ │ φ(A) │ │                            │
│  │ │ =2.1 │ │               │ │ =0.3 │ │                            │
│  │ └──────┘ │               │ └──────┘ │                            │
│  └──────────┘               └──────────┘                            │
│                                                                     │
│  When φ(B) > 8 on Node A:                                          │
│    → A marks B as DOWN in its local failure detector                │
│    → A gossips "B is DOWN" to other nodes                           │
│    → Hints are stored for B's writes                                │
│    → Read/write requests route around B                             │
│                                                                     │
│  Monitoring:                                                        │
│    nodetool info → shows phi values for all peers                   │
│    JMX: org.apache.cassandra.net:type=FailureDetector               │
│                                                                     │
│  Production tuning:                                                 │
│    • Cross-DC: increase phi_convict_threshold to 10-12              │
│    • Unstable network: increase to 10-12                            │
│    • Co-located (same rack): can decrease to 5-6                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Akka Cluster

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AKKA CLUSTER FAILURE DETECTION                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Configuration (application.conf):                                  │
│  ─────────────────────────────────                                  │
│    akka.cluster.failure-detector {                                   │
│      implementation-class =                                         │
│        "akka.remote.PhiAccrualFailureDetector"                      │
│      threshold = 8.0                                                │
│      max-sample-size = 1000                                         │
│      min-std-deviation = 100 ms                                     │
│      acceptable-heartbeat-pause = 3 s                               │
│      heartbeat-interval = 1 s                                       │
│      expected-response-after = 1 s                                  │
│    }                                                                │
│                                                                     │
│  Uses NORMAL distribution (Gaussian CDF)                            │
│  Includes min-std-deviation floor to prevent over-sensitivity       │
│  acceptable-heartbeat-pause: accounts for GC pauses                 │
│                                                                     │
│  Node lifecycle driven by φ:                                        │
│    Joining → Up → (φ exceeds threshold) → Unreachable → Down       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.3 Other Implementations

| System | Distribution | Default φ | Window | Notes |
|--------|-------------|-----------|--------|-------|
| Cassandra | Exponential | 8 | 1000 | Gossip-integrated |
| Akka | Normal | 8 | 1000 | min-std-deviation=100ms |
| Apache Spark | Normal | 8 | — | Executor heartbeats |
| Hazelcast | Normal | 10 | 200 | More conservative |
| ScyllaDB | Exponential | 8 | 1000 | Cassandra-compatible |
| CockroachDB | — | — | — | Uses different approach (liveness leases) |

---

## 9. SWIM Protocol Alternative

### 9.1 SWIM (Scalable Weakly-consistent Infection-style Membership)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SWIM PROTOCOL OVERVIEW                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Instead of all-to-all heartbeats, SWIM uses:                       │
│  1. Random probe: Each node pings one random peer per interval      │
│  2. Indirect probes: If direct probe fails, ask k others to probe   │
│                                                                     │
│  ┌─────┐  ping   ┌─────┐                                           │
│  │  A  │────────→│  B  │  Direct probe                              │
│  └─────┘         └─────┘                                            │
│     │                ✗ (no response)                                 │
│     │                                                                │
│     │  ping-req  ┌─────┐  ping   ┌─────┐                            │
│     │───────────→│  C  │────────→│  B  │  Indirect probe             │
│     │            └─────┘         └─────┘                             │
│     │  ping-req  ┌─────┐  ping   ┌─────┐                            │
│     │───────────→│  D  │────────→│  B  │  Indirect probe             │
│     │            └─────┘         └─────┘                             │
│     │                                                                │
│  If all probes fail → B is suspected → (timeout) → B is declared    │
│  failed → disseminated via piggyback gossip                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Comparison

```
┌──────────────────────┬───────────────────────┬───────────────────────┐
│  Dimension           │  Phi Accrual          │  SWIM                 │
├──────────────────────┼───────────────────────┼───────────────────────┤
│  Network overhead    │  O(n²) heartbeats     │  O(n) probes          │
│  Detection output    │  Continuous φ         │  Binary (suspect/dead)│
│  Scalability         │  Poor (>1000 nodes)   │  Excellent            │
│  Accuracy            │  Very high            │  Good (indirect helps)│
│  Network partition   │  Detect fast          │  Detect fast          │
│  Asymmetric failure  │  Poor (one-way)       │  Good (multi-path)    │
│  Adaptability        │  Self-tuning          │  Fixed timeouts       │
│  Implementation      │  Moderate             │  Complex              │
│  Best for            │  <1000 nodes,         │  >1000 nodes,         │
│                      │  varied networks      │  homogeneous network  │
└──────────────────────┴───────────────────────┴───────────────────────┘
```

### 9.3 When to Use Which

```
  Use PHI ACCRUAL when:                    Use SWIM when:
  ─────────────────────                    ──────────────
  • Cluster < 1000 nodes                   • Cluster > 1000 nodes
  • Heterogeneous network                  • Homogeneous network
  • Need tunable false-positive rate       • Need O(n) scalability
  • Cross-datacenter deployment            • Single datacenter
  • Applications need different            • Simple alive/dead is enough
    sensitivity levels                     • Need path diversity (indirect
  • Network conditions change                probes detect asymmetric
    frequently                               failures)
  
  HYBRID: Some systems use phi accrual for nearby nodes
          and SWIM-style probing for large-scale membership.
          (e.g., Serf/Consul uses SWIM, Cassandra uses phi accrual)
```

---

## 10. Implementation Considerations

### 10.1 Clock Resolution

```
  Problem: If system clock resolution is poor, inter-arrival measurements
           become inaccurate.
  
  Requirements:
  ┌──────────────────────────────────────────────────────────────┐
  │  Heartbeat interval   │  Required clock resolution           │
  ├───────────────────────┼──────────────────────────────────────┤
  │  1 second             │  ≤ 10ms (1% of interval)             │
  │  100ms                │  ≤ 1ms                               │
  │  10ms                 │  ≤ 100μs                             │
  └───────────────────────┴──────────────────────────────────────┘
  
  Modern OS: System.nanoTime() (Java), clock_gettime(MONOTONIC) (Linux)
  → microsecond resolution, sufficient for all practical intervals
  
  CRITICAL: Use MONOTONIC clock, not wall clock!
  Wall clock can jump (NTP adjustment, leap seconds) → corrupts statistics
```

### 10.2 Memory Requirements

```
  Per monitored node:
    Window of 1000 doubles = 8KB
    Running statistics      = 32 bytes
    Last heartbeat time     = 8 bytes
    Total                   ≈ 8KB per peer
  
  In a 100-node cluster, each node monitors 99 peers:
    99 × 8KB ≈ 792KB  (negligible)
  
  In a 1000-node cluster:
    999 × 8KB ≈ 8MB   (still fine)
```

### 10.3 Edge Cases

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EDGE CASES                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. NODE RESTART                                                    │
│     Problem: Old window has stale data from before restart          │
│     Solution: Clear window on connection re-establishment           │
│               Use generation counter in heartbeat protocol          │
│                                                                     │
│  2. NETWORK PARTITION vs CRASH                                      │
│     Problem: Both look identical (no heartbeats arrive)             │
│     Reality: CANNOT distinguish with phi accrual alone              │
│     Mitigation: Combine with quorum-based detection                 │
│       "If >50% of cluster reports node dead → actually dead"        │
│       "If only I report it dead → maybe I'm partitioned"            │
│                                                                     │
│  3. CLOCK SKEW (distributed timestamps)                             │
│     Problem: Using remote timestamps is unreliable                  │
│     Solution: Only use LOCAL receive timestamps                     │
│               Never rely on sender's clock                          │
│                                                                     │
│  4. BURST HEARTBEATS AFTER PAUSE                                    │
│     Problem: After GC pause, multiple queued heartbeats arrive      │
│              at once → inter-arrival = 0 → corrupts statistics      │
│     Solution: Ignore inter-arrivals < threshold (e.g., < 10ms)      │
│               Or take max(inter_arrival, min_interval)              │
│                                                                     │
│  5. VERY FIRST HEARTBEAT                                            │
│     Problem: Can't compute inter-arrival from one sample            │
│     Solution: Use bootstrap values until 2nd heartbeat              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Tuning Guide for Production

### 11.1 Configuration Parameters

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION TUNING MATRIX                               │
├──────────────────────┬────────────┬──────────────────────────────────────┤
│  Parameter           │  Default   │  Guidance                            │
├──────────────────────┼────────────┼──────────────────────────────────────┤
│  φ threshold         │  8         │  Cross-DC: 10-12                     │
│                      │            │  Same rack: 5-6                      │
│                      │            │  Unstable net: 10-12                 │
├──────────────────────┼────────────┼──────────────────────────────────────┤
│  Window size         │  1000      │  More = more accurate, slower adapt  │
│                      │            │  Less = faster adapt, more noise     │
│                      │            │  Range: 100-10000                    │
├──────────────────────┼────────────┼──────────────────────────────────────┤
│  Min std deviation   │  100ms     │  Prevents over-sensitivity on stable │
│                      │            │  networks. Increase for GC-prone JVM │
│                      │            │  Range: 50ms-500ms                   │
├──────────────────────┼────────────┼──────────────────────────────────────┤
│  Heartbeat interval  │  1s        │  Faster = quicker detection, more    │
│                      │            │  network overhead                    │
│                      │            │  Range: 100ms-5s                     │
├──────────────────────┼────────────┼──────────────────────────────────────┤
│  Acceptable pause    │  3s        │  Must exceed worst-case GC pause     │
│                      │            │  Check GC logs for P99.9 pause time  │
│                      │            │  Range: 1s-30s                       │
└──────────────────────┴────────────┴──────────────────────────────────────┘
```

### 11.2 Monitoring in Production

```
  Essential metrics to expose:
  ─────────────────────────────
  • phi_current{peer="nodeB"}         — current φ value per peer
  • phi_max_1m{peer="nodeB"}          — max φ in last minute
  • heartbeat_inter_arrival_mean_ms   — current μ per peer
  • heartbeat_inter_arrival_stddev_ms — current σ per peer
  • false_positive_count              — convictions followed by recovery
  
  Alert thresholds:
  ─────────────────
  • WARN:  φ > threshold/2 sustained for >30s (node is struggling)
  • ALERT: φ > threshold (node convicted)
  • INFO:  μ drift > 2x baseline (network degradation)
  
  Dashboard layout:
  ┌──────────────────────────────────────────────────┐
  │  Node B - Phi Accrual Status                     │
  │  ────────────────────────────                    │
  │  Current φ: ████░░░░░░░░░░░░ 3.2 / 8.0          │
  │  Mean interval: 1023ms (expected: 1000ms)        │
  │  Std deviation: 87ms                             │
  │  Samples: 1000/1000                              │
  │  Last heartbeat: 1.8s ago                        │
  │  Status: ALIVE (healthy)                         │
  └──────────────────────────────────────────────────┘
```

---

## 12. Architect's Guide

### 12.1 Decision Framework

```
┌─────────────────────────────────────────────────────────────────────────┐
│              FAILURE DETECTION SELECTION GUIDE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Q1: How many nodes?                                                    │
│  ├── < 100:  Any approach works                                         │
│  ├── 100-1000: Phi accrual (manageable overhead)                        │
│  └── > 1000: SWIM or hierarchical phi accrual                           │
│                                                                         │
│  Q2: Network homogeneity?                                               │
│  ├── Homogeneous (same DC): Fixed timeout is acceptable                 │
│  └── Heterogeneous (multi-DC): Phi accrual strongly preferred           │
│                                                                         │
│  Q3: GC pauses expected?                                                │
│  ├── Yes (JVM, .NET): Phi accrual (absorbs pauses naturally)            │
│  └── No (Go, Rust, C): Fixed timeout may suffice                        │
│                                                                         │
│  Q4: Need different detection sensitivity for different consumers?       │
│  ├── Yes: Phi accrual (by design)                                       │
│  └── No: Either approach                                                │
│                                                                         │
│  Q5: Asymmetric network failure detection needed?                       │
│  ├── Yes: SWIM (indirect probes detect one-way failures)                │
│  └── No: Phi accrual                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Integration Patterns

```
  Pattern 1: DIRECT INTEGRATION (Cassandra-style)
  ────────────────────────────────────────────────
  ┌─────────────────────┐
  │   Application       │
  │   ┌───────────────┐ │
  │   │ Phi Detector  │ │ ← Embedded in each node
  │   │ (per peer)    │ │
  │   └───────────────┘ │
  │   ┌───────────────┐ │
  │   │ Gossip Layer  │ │ ← Heartbeats via gossip protocol
  │   └───────────────┘ │
  └─────────────────────┘
  
  Pattern 2: SIDECAR / SERVICE MESH
  ──────────────────────────────────
  ┌──────────┐    ┌──────────────────┐
  │   App    │◄──►│  Failure Detect  │ ← Sidecar process
  │          │    │  Service (phi)   │    monitors all peers
  └──────────┘    └──────────────────┘    reports via local API
  
  Pattern 3: CENTRALIZED MONITOR
  ──────────────────────────────
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ Node A  │  │ Node B  │  │ Node C  │
  └────┬────┘  └────┬────┘  └────┬────┘
       │ heartbeat   │            │
       ▼             ▼            ▼
  ┌──────────────────────────────────────┐
  │   Centralized Failure Detector       │ ← Single point of failure!
  │   (phi accrual for each node)        │    Use only with HA pair
  └──────────────────────────────────────┘
  
  Pattern 4: HIERARCHICAL (large-scale)
  ──────────────────────────────────────
  ┌─────────────────────────────────────────────────┐
  │  Cross-DC: SWIM protocol (scalable, O(n))       │
  │  ┌─────────────────────────────────────────┐    │
  │  │  Intra-DC: Phi accrual (accurate, O(n²))│    │
  │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │    │
  │  │  │  A  │ │  B  │ │  C  │ │  D  │       │    │
  │  │  └─────┘ └─────┘ └─────┘ └─────┘       │    │
  │  └─────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────┘
```

### 12.3 Common Pitfalls

```
  1. USING φ=1 OR φ=2 IN PRODUCTION
     → Constant false positives, cluster instability
     → Minimum recommended: φ=5 for production
  
  2. NOT ACCOUNTING FOR GC PAUSES
     → Set min_std_deviation > max_gc_pause / 4
     → Or use acceptable-heartbeat-pause (Akka)
  
  3. SMALL WINDOW + VARIABLE NETWORK
     → Window fills with one condition, network changes, mass convictions
     → Use window ≥ 500 for production
  
  4. TRUSTING PHI ALONE FOR PARTITION DETECTION
     → Phi can't distinguish "they're dead" from "I'm isolated"
     → Always combine with quorum/majority agreement
  
  5. NOT RESETTING ON RECONNECTION
     → Stale statistics from before network event
     → Clear window when connection re-established
```

---

## References

1. Hayashibara, N., Défago, X., Yared, R., & Katayama, T. (2004). "The φ Accrual Failure Detector." *IEEE Symposium on Reliable Distributed Systems (SRDS)*.
2. Apache Cassandra source: `org.apache.cassandra.gms.FailureDetector`
3. Akka documentation: Cluster Membership - Failure Detector
4. Das, A., Gupta, I., & Motivala, A. (2002). "SWIM: Scalable Weakly-consistent Infection-style Process Group Membership Protocol."
5. Chandra, T. D., & Toueg, S. (1996). "Unreliable Failure Detectors for Reliable Distributed Systems." *JACM*.
