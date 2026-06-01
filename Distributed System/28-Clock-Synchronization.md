# Clock Synchronization in Distributed Systems

## 1. Why Clocks Matter

Without synchronized clocks, distributed systems have no shared notion of "now."

**Critical dependencies on time:**

| Use Case | Impact of Skew |
|----------|---------------|
| Event ordering | Causal violations, lost updates |
| TTL / Expiry | Premature eviction or stale data served |
| Lease validity | Split-brain (two leaders) |
| Certificate expiration | TLS handshake failures |
| Log correlation | Impossible debugging across services |
| Cache invalidation | Serving stale or evicting fresh data |
| Distributed transactions | Consistency violations |
| Rate limiting | Over/under enforcement |

```
  Service A (clock: 10:00:00.000)        Service B (clock: 10:00:00.150)
  ┌─────────────────────────┐            ┌─────────────────────────┐
  │ Event X at 10:00:00.100 │            │ Event Y at 10:00:00.080 │
  └─────────────────────────┘            └─────────────────────────┘
                │                                      │
                └──────────── Which happened first? ───┘
                     
  Real order:  X happened BEFORE Y
  Clock order: Y (080) appears before X (100) — WRONG!
```

A 150ms skew means any events within a 150ms window cannot be reliably ordered using timestamps alone.

---

## 2. Types of Clocks

### 2a. Physical Clocks (Wall-Clock / Time-of-Day)

Attempts to track real-world time (UTC). Returned by `System.currentTimeMillis()`, `time.time()`, `gettimeofday()`.

**Quartz Oscillator Characteristics:**
- Crystal vibrates at ~32,768 Hz
- Drift: 10–100 ppm (parts per million)
- 1 ppm = 86.4 ms/day
- 100 ppm = 8.64 seconds/day

```
  Drift Factors:
  ┌────────────────────────────────────────────────┐
  │  Temperature  ──→  +/- 0.035 ppm/°C²          │
  │  Voltage      ──→  frequency pulling           │
  │  Aging        ──→  ~1 ppm/year (crystal stress)│
  │  Vibration    ──→  phase noise                 │
  └────────────────────────────────────────────────┘
```

**Problems with wall clocks:**
- NTP can step clock backward → breaks elapsed-time measurements
- Leap seconds cause discontinuities
- VM migrations cause jumps
- Not monotonic

### 2b. Monotonic Clocks

Always increasing counter for measuring **elapsed time**. Returned by `clock_gettime(CLOCK_MONOTONIC)`, `System.nanoTime()`.

```
  Wall Clock:      10:00:00 → 10:00:01 → 09:59:59 (NTP step back!)
  Monotonic Clock: 1000000  → 1001000  → 1002000  (always forward)
```

**Properties:**
- Unaffected by NTP adjustments
- Meaningless across machines (different epoch per boot)
- Rate may be adjusted (NTP slew) but never jumps backward
- Perfect for timeouts, intervals, benchmarks

### 2c. Logical Clocks

Do not measure real time—capture **causal ordering**.
- **Lamport Clocks**: single integer, partial order
- **Vector Clocks**: vector of integers, detect concurrency
- Covered in separate document (29-Logical-Clocks.md)

---

## 3. Clock Skew vs Clock Drift

```
  Clock
  Value
    ▲
    │          Real Time (perfect clock)
    │         ╱
    │        ╱  ← Drift = slope difference
    │       ╱
    │      ╱........... Fast clock (drift > 0)
    │     ╱    .....
    │    ╱ ....        ← Skew at time T
    │   ╱..            (instantaneous difference)
    │  ╱
    │ ╱
    │╱  ............... Slow clock (drift < 0)
    │         ......
    │    .....
    │....
    ├──────────────────────────────► Real Time
    0         T₁        T₂
    
    Skew(T₁) = small
    Skew(T₂) = large  ← accumulates due to drift!
```

| Term | Definition | Unit |
|------|-----------|------|
| **Skew** | Difference between two clocks at an instant | seconds |
| **Drift** | Rate of deviation from reference clock | ppm (parts per million) |
| **Drift rate** | Rate of change of drift | ppm/sec |

**Key insight:** If drift = ρ ppm, then after time t, maximum skew = ρ × t.

To keep skew < δ, must re-synchronize every δ/ρ seconds.

Example: drift = 50 ppm, target max skew = 10ms
- Re-sync interval = 10ms / 50μs-per-second = 200 seconds

---

## 4. NTP (Network Time Protocol)

### Stratum Hierarchy

```
                    ┌─────────────────┐
                    │  Stratum 0      │
                    │  (Reference)    │
                    │  Atomic Clocks  │
                    │  GPS Receivers  │
                    └────────┬────────┘
                             │ Direct hardware connection
                    ┌────────▼────────┐
                    │  Stratum 1      │
                    │  Primary Servers│
                    │  (≈1000 global) │
                    └───┬────┬────┬───┘
                        │    │    │
              ┌─────────┘    │    └─────────┐
              │              │              │
     ┌────────▼───┐  ┌──────▼─────┐  ┌────▼────────┐
     │ Stratum 2  │  │ Stratum 2  │  │ Stratum 2   │
     │ Secondary  │  │ Secondary  │  │ Secondary   │
     └──┬─────┬───┘  └──┬─────┬───┘  └──┬──────┬───┘
        │     │          │     │          │      │
     ┌──▼──┐┌─▼──┐   ┌──▼──┐┌─▼──┐   ┌──▼──┐┌──▼──┐
     │ S3  ││ S3 │   │ S3  ││ S3 │   │ S3  ││ S3  │
     └─────┘└────┘   └─────┘└────┘   └─────┘└─────┘
     
     Max depth: Stratum 15 (Stratum 16 = unsynchronized)
```

### Cristian's Algorithm (Basis of NTP)

```
  Client                          Server
    │                               │
    │──── Request (t₁) ───────────►│
    │                               │
    │                               │ Server time = t_s
    │                               │
    │◄─── Response (t₂) ──────────│
    │                               │
    
  Round-trip delay: RTT = t₂ - t₁
  Estimated one-way delay: δ = RTT / 2
  Estimated server time now: t_s + δ
  Clock offset: θ = t_s + δ - t₂
  
  Problem: Assumes symmetric delays!
  Reality: upload ≠ download latency
```

### NTP Four-Timestamp Exchange

```
  Client                            Server
    │                                 │
    │  t₁ (client send)              │
    │──────── Request ───────────────►│
    │                                 │ t₂ (server receive)
    │                                 │ t₃ (server send)
    │◄──────── Response ─────────────│
    │  t₄ (client receive)           │
    │                                 │
    
  Offset θ = [(t₂ - t₁) + (t₃ - t₄)] / 2
  Delay  δ = (t₄ - t₁) - (t₃ - t₂)
  
  NTP selects from multiple servers, filters outliers,
  uses intersection algorithm for best estimate.
```

### Step vs Slew Adjustment

| Adjustment | When Used | Behavior |
|-----------|-----------|----------|
| **Slew** | offset < 128ms | Gradually adjust rate (±500 ppm max) |
| **Step** | offset > 128ms | Instant jump (dangerous for applications) |
| **Panic** | offset > 1000s | ntpd exits (refuses to correct) |

**Slew implications:**
- 128ms offset at 500ppm slew → takes ~256 seconds to converge
- Applications see no discontinuity
- Monotonic clock rate subtly changes

### NTP Accuracy

| Environment | Typical Accuracy |
|------------|-----------------|
| Internet (multi-hop) | 1–50 ms |
| Corporate LAN | 0.1–1 ms |
| Dedicated NTP on LAN | 10–100 μs |
| With hardware timestamping | 1–10 μs |

### Limitations

1. **Asymmetric delays**: If upload=10ms, download=1ms, NTP estimates 5.5ms each → 4.5ms error
2. **Congestion**: Queuing delays vary packet-to-packet
3. **OS scheduling**: Kernel-to-user timestamp delay
4. **Software timestamping**: Interrupt latency adds jitter
5. **No bound on error**: NTP gives best-effort, no guarantees

---

## 5. PTP (Precision Time Protocol — IEEE 1588)

### Architecture

```
  ┌──────────────────────────────────────────────────────────┐
  │                    PTP Domain                             │
  │                                                          │
  │  ┌────────────┐     ┌────────────┐     ┌────────────┐   │
  │  │Grandmaster │     │ Boundary   │     │ Boundary   │   │
  │  │   Clock    │────►│   Clock    │────►│   Clock    │   │
  │  │(GPS/Atomic)│     │ (Switch)   │     │ (Switch)   │   │
  │  └────────────┘     └─────┬──────┘     └─────┬──────┘   │
  │                           │                   │          │
  │                     ┌─────┴─────┐       ┌─────┴─────┐   │
  │                     │           │       │           │   │
  │                  ┌──▼──┐  ┌──▼──┐   ┌──▼──┐  ┌──▼──┐  │
  │                  │Slave│  │Slave│   │Slave│  │Slave│  │
  │                  │Clock│  │Clock│   │Clock│  │Clock│  │
  │                  └─────┘  └─────┘   └─────┘  └─────┘  │
  └──────────────────────────────────────────────────────────┘
```

### Key Differentiators from NTP

| Feature | NTP | PTP |
|---------|-----|-----|
| Timestamping | Software (kernel) | Hardware (NIC PHY) |
| Accuracy | 1–10 ms | 10–100 ns |
| Network support | Any | Requires PTP-aware switches |
| Cost | Free | Specialized hardware |
| Standards | RFC 5905 | IEEE 1588-2019 |

### Hardware Timestamping

```
  ┌─────────────────────────────────────────────────┐
  │ Network Interface Card (NIC)                    │
  │                                                 │
  │  ┌─────────┐    ┌──────────┐    ┌──────────┐   │
  │  │   PHY   │───►│Timestamp │───►│   MAC    │   │
  │  │(Physical│    │  Unit    │    │Controller│   │
  │  │ Layer)  │    │(captures │    │          │   │
  │  └─────────┘    │ at wire) │    └──────────┘   │
  │                 └──────────┘                    │
  │                      │                          │
  │                      ▼                          │
  │              Nanosecond-precise                  │
  │              timestamp register                  │
  └─────────────────────────────────────────────────┘
  
  Eliminates: OS scheduling jitter, kernel stack delays,
              interrupt latency, context switches
```

### Use Cases
- **Financial trading**: MiFID II mandates ≤100μs accuracy for trade timestamps
- **Telecom (5G)**: Time-sensitive networking for radio synchronization
- **Power grid**: Synchrophasors require <1μs
- **Data centers**: Google, Meta use PTP internally

---

## 6. Google's TrueTime API

### The Key Insight

Instead of pretending clocks are exact, **expose the uncertainty**.

```
  Traditional Clock API:
    now() → single timestamp T
    (lies: actual time could be anywhere in an unknown range)
    
  TrueTime API:
    TT.now() → TTinterval [earliest, latest]
    TT.after(t) → true if t is definitely in the past
    TT.before(t) → true if t is definitely in the future
```

### Infrastructure

```
  ┌─────────────────────────────────────────────────────────┐
  │                   Google Datacenter                      │
  │                                                         │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
  │  │ GPS      │  │ GPS      │  │ Atomic   │  ← Time      │
  │  │ Receiver │  │ Receiver │  │ Clock    │    Masters    │
  │  │ (Armageddon│ │         │  │(Rubidium)│              │
  │  │  Master) │  │         │  │          │              │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
  │       │              │              │                    │
  │       └──────────────┼──────────────┘                    │
  │                      │                                   │
  │              ┌───────▼───────┐                           │
  │              │  Time Daemon  │  ← Every server           │
  │              │  (timeslave)  │     polls multiple masters │
  │              └───────┬───────┘                           │
  │                      │                                   │
  │              ┌───────▼───────┐                           │
  │              │  Application  │                           │
  │              │  TT.now() →   │                           │
  │              │  [earliest,   │                           │
  │              │   latest]     │                           │
  │              └───────────────┘                           │
  └─────────────────────────────────────────────────────────┘
  
  GPS: diverse manufacturers (avoid correlated failures)
  Atomic: provides holdover when GPS signal lost
  Multiple masters: Marzullo's algorithm for intersection
```

### Uncertainty Bounds

```
  Typical ε (epsilon / uncertainty):
  
  Between syncs:
  ε grows at ~200 μs/sec (worst-case local drift)
  
  After sync (every 30s):
  ε resets to ~1-4 ms (network delay + processing)
  
  ε (ms)
  7 ┤                                              .
    │                                           ...
  4 ┤.                          .            ...
    │  ...                       ...      ...
  1 ┤     ...    sync              ...sync
    │        .↓..    .               .
    ├─────────────────────────────────────────► time
         30s       30s          30s
         
  Sawtooth pattern: ε shrinks at sync, grows between syncs
```

### Spanner's Commit-Wait

```
  Transaction commits at TrueTime = [earliest, latest]
  
  Timeline:
  ───────────────────────────────────────────────────►
  
       TT.now() returns [e, l]
       │◄──── ε ────►│
       e              l
       │              │
       │   Commit     │
       │   timestamp  │
       │   = s = l    │── assign latest as commit time
       │              │
       │              │──── Wait until TT.after(s) ─────│
       │              │         (wait out ε)            │
       │              │                                 │
       │              │◄─────── commit-wait ──────────►│
       │                                               │
       │                                    Now safe:  │
       │                                    Real time  │
       │                                    is past s  │
  
  Why this works:
  - Assign s = latest bound of TT.now()
  - Wait until TT.after(s) = true
  - Guarantee: real time > s after wait
  - Therefore: any later transaction will get timestamp > s
  - Result: timestamp order = real-time order (external consistency!)
  
  Cost: average wait = 2ε ≈ 7-14ms (small for Spanner's use case)
```

### Why TrueTime "Solves" Clock Sync

It doesn't eliminate uncertainty—it **makes uncertainty explicit and bounded**, then **waits it out**. The system trades latency (commit-wait) for correctness (external consistency / linearizability).

---

## 7. Amazon Time Sync Service

### Architecture

```
  ┌────────────────────────────────────────────────┐
  │             AWS Availability Zone               │
  │                                                 │
  │  ┌─────────────────────────────────┐            │
  │  │    Amazon Time Sync Service     │            │
  │  │    (Satellite-connected clocks  │            │
  │  │     in each AZ)                 │            │
  │  └──────────────┬──────────────────┘            │
  │                 │ NTP / PTP                     │
  │      ┌──────────┼──────────┐                    │
  │      │          │          │                    │
  │  ┌───▼──┐  ┌───▼──┐  ┌───▼──┐                  │
  │  │ EC2  │  │ EC2  │  │ EC2  │                  │
  │  │      │  │      │  │      │                  │
  │  │Clock │  │Clock │  │Clock │                  │
  │  │Bound │  │Bound │  │Bound │                  │
  │  └──────┘  └──────┘  └──────┘                  │
  └────────────────────────────────────────────────┘
```

### ClockBound Library

Similar concept to TrueTime—provides bounded intervals:

```go
// ClockBound API
cb := clockbound.New()
now_bound := cb.Now()  // returns {earliest, latest}

// Check if a timestamp is definitely in the past
if cb.After(timestamp) {
    // safe to proceed
}
```

### Features
- **Leap-second smearing**: Spreads leap second over 24 hours (avoids 23:59:60)
- **Microsecond accuracy** within AWS (using PTP where available)
- **Accessible at 169.254.169.123** (link-local, zero-hop)
- **Chrony-based** client on Amazon Linux

---

## 8. Facebook/Meta's Approach

### Architecture

```
  ┌──────────────────────────────────────────────────┐
  │           Meta Timing Infrastructure             │
  │                                                  │
  │  Tier 1: GPS + Atomic (Stratum 1)               │
  │  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐       │
  │  │GPS+Rb │ │GPS+Rb │ │GPS+Cs │ │GPS+Rb │       │
  │  └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘       │
  │      │         │         │         │            │
  │  Tier 2: Regional Time Servers (Stratum 2)      │
  │  ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐       │
  │  │Chrony │ │Chrony │ │Chrony │ │Chrony │       │
  │  │Server │ │Server │ │Server │ │Server │       │
  │  └───┬───┘ └───┬───┘ └───┬───┘ └───┬───┘       │
  │      │         │         │         │            │
  │  Tier 3: All production servers (Stratum 3)     │
  │  ┌───▼───┐ ┌───▼───┐ ┌───▼───┐ ┌───▼───┐       │
  │  │Chrony │ │Chrony │ │Chrony │ │Chrony │       │
  │  │Client │ │Client │ │Client │ │Client │       │
  │  └───────┘ └───────┘ └───────┘ └───────┘       │
  └──────────────────────────────────────────────────┘
```

### Why Chrony over ntpd

| Feature | ntpd | Chrony |
|---------|------|--------|
| Initial sync speed | Minutes | Seconds |
| Intermittent connectivity | Poor | Excellent |
| VM/container support | Poor | Good |
| Temperature compensation | No | Yes |
| Memory footprint | Higher | Lower |
| Accuracy (LAN) | ~100 μs | ~10 μs |

### Monitoring at Scale
- Custom metrics pipeline for clock health
- Alerting when offset > threshold (typically 10ms)
- Automated remediation (restart chrony, escalate)
- Tracking NTP response times, jitter, stratum changes

---

## 9. The Problem with Physical Time in Distributed Systems

### Ordering Violations

```
  Machine A (clock +50ms fast)        Machine B (clock accurate)
  ─────────────────────────────       ─────────────────────────
  
  Real time 100ms:
    Write X = "hello" 
    Timestamp: 150ms  ←── (100 + 50 skew)
    
                            Real time 120ms:
                              Write X = "world"
                              Timestamp: 120ms
  
  LWW Resolution: max timestamp wins
    → X = "hello" (timestamp 150 > 120)
    
  Reality: "world" was written LATER and should win!
    → Correct answer: X = "world"
    
  ┌─────────────────────────────────────────────┐
  │  CLOCK SKEW CAUSED SILENT DATA LOSS!        │
  │  "world" was the latest write but was       │
  │  overwritten by the stale "hello"           │
  └─────────────────────────────────────────────┘
```

### Lease Expiry Race

```
  Leader                              Follower
  (clock slow by 5s)                  (clock accurate)
  ─────────────────                   ─────────────────
  
  Acquires lease at T=0
  Lease expires at T=10s
  
  Leader's clock at real T=10:
    Shows T=5 → "lease still valid!"     Follower's clock: T=10
    Continues acting as leader ──┐        "Lease expired!"
                                 │        Becomes new leader ──┐
                                 │                             │
                                 ▼                             ▼
                          ┌─────────────────────────────────────┐
                          │         SPLIT BRAIN!                 │
                          │    Two leaders simultaneously       │
                          │    Data corruption possible         │
                          └─────────────────────────────────────┘
  
  Mitigation: Lease holder must use SHORTER timeout than observers
              (leader renews at T-skew_bound, observers wait T+skew_bound)
```

### Certificate Expiry with Skew

```
  Server (clock accurate)            Client (clock 2 min ahead)
  
  Certificate valid: 10:00 - 10:05
  
  Real time: 10:03
  Server: "cert valid, 2 min left"
  Client: "my clock says 10:05, CERT EXPIRED!" → TLS failure
```

---

## 10. Hybrid Approaches

### HLC (Hybrid Logical Clock)

Combines physical time with logical counter to ensure:
1. Timestamps close to real time (useful for humans/TTL)
2. Causal ordering preserved (like Lamport clocks)
3. Unique timestamps (counter breaks ties)

```
  HLC Timestamp: (physical_time, logical_counter, node_id)
  
  Algorithm for send/local event:
    l' = max(local_physical_time, hlc.l)
    if l' == hlc.l:
        c' = hlc.c + 1    // same physical time, increment counter
    else:
        c' = 0            // new physical time, reset counter
    hlc = (l', c')
    
  Algorithm for receive(msg_hlc):
    l' = max(local_physical_time, hlc.l, msg_hlc.l)
    if l' == hlc.l == msg_hlc.l:
        c' = max(hlc.c, msg_hlc.c) + 1
    elif l' == hlc.l:
        c' = hlc.c + 1
    elif l' == msg_hlc.l:
        c' = msg_hlc.c + 1
    else:
        c' = 0
    hlc = (l', c')
```

**Properties:**
- HLC ≥ physical time always (bounded by max skew in the system)
- If e happened-before f, then HLC(e) < HLC(f)
- Compact: fits in 64 bits (48 bits physical + 16 bits counter)

### Confidence Intervals (TrueTime-style)

```
  Instead of: timestamp = 42
  Use:        timestamp = [40, 44]  (± uncertainty)
  
  Comparison:
  
  Event A: [40 ──────── 44]
  Event B:          [43 ──────── 47]
                    ^^
                    OVERLAP → cannot determine order
                    
  Event A: [40 ── 44]
  Event C:              [50 ── 54]
                        ^^
                        NO OVERLAP → A definitely before C
```

### Bounded Clock Skew Assumption

Many systems assume a maximum clock skew ε and design around it:
- If skew > ε, system may violate invariants
- Must monitor and alert
- CockroachDB: rejects transactions if detected skew > max-offset (default 500ms)

---

## 11. Real-World Implementations

### Comparison Matrix

```
┌───────────────┬──────────────┬───────────────┬──────────────┬───────────┐
│   System      │ Clock Source │   Mechanism   │  Accuracy    │  Tradeoff │
├───────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Google        │ GPS + Atomic │ TrueTime      │ ~1-7 ms      │ Commit    │
│ Spanner       │              │ (intervals)   │ uncertainty  │ latency   │
├───────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ CockroachDB   │ NTP          │ HLC + max     │ ~100-500 ms  │ Rejects   │
│               │              │ offset check  │ assumed      │ on skew   │
├───────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Cassandra     │ Client NTP   │ LWW with      │ Varies       │ Silent    │
│               │              │ client TS     │ (uncontrolled)│ data loss │
├───────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ DynamoDB      │ AWS Time     │ Server-side   │ Microseconds │ AWS-only  │
│               │ Sync         │ TTL           │              │           │
├───────────────┼──────────────┼───────────────┼──────────────┼───────────┤
│ Financial     │ PTP + GPS    │ Hardware TS   │ <100 ns      │ Expensive │
│ Exchanges     │              │               │              │ hardware  │
└───────────────┴──────────────┴───────────────┴──────────────┴───────────┘
```

### Google Spanner

- TrueTime GPS + atomic clocks in every datacenter
- Commit-wait ensures external consistency (linearizability)
- Enables globally-consistent reads at a timestamp
- Read-only transactions: pick timestamp, read anywhere without locks
- Schema: `ALLOW_COMMIT_TIMESTAMP` columns

### CockroachDB

- Uses HLC (Hybrid Logical Clock)
- Configurable `--max-offset` (default 500ms)
- If node detects clock skew > 80% of max-offset → node self-terminates
- Uncertainty intervals on reads: if read encounters value in [read_ts - max_offset, read_ts], must restart at higher timestamp
- Cannot provide true external consistency (only serializable)

### Cassandra (LWW)

```
  Client A writes: UPDATE users SET name='Alice' USING TIMESTAMP 1000;
  Client B writes: UPDATE users SET name='Bob'   USING TIMESTAMP 999;
  
  Cassandra keeps: name='Alice' (higher timestamp wins)
  
  Problem: If Client B's clock was slow, Bob's write was actually later
           but Cassandra has no way to know → silent data loss
           
  Mitigation: Use server-side timestamps (USING TIMESTAMP not recommended)
```

### Financial Exchanges (MiFID II)

- **Requirement**: Timestamps accurate to 100 microseconds for most instruments
- **Implementation**: PTP with GPS grandmaster clocks
- **Audit**: Must prove timestamp accuracy to regulators
- **Hardware**: Dedicated timing cards (e.g., Meinberg, Spectracom)

---

## 12. Operational Concerns

### Monitoring Clock Health

```bash
# Check NTP sync status
$ chronyc tracking
Reference ID    : A9FEA97B (169.254.169.123)
Stratum         : 3
Ref time (UTC)  : Thu Jan 01 12:00:00 2024
System time     : 0.000000123 seconds fast of NTP time
Last offset     : +0.000000089 seconds
RMS offset      : 0.000000534 seconds
Root delay      : 0.000234 seconds
Root dispersion : 0.000045 seconds
Leap status     : Normal

# Check sources
$ chronyc sources -v
  .-- Source mode  '^' = server, '=' = peer, '#' = local clock.
  / .- Source state '*' = current, '+' = combined, '-' = not combined,
 | /               'x' = may be in error, '~' = too variable.
 ||                                                 .- xxxx [ yyyy ] +/- zzzz
 ||      Reachability register (octal) -.           |  xxxx = adjusted offset,
 ||      Log2(Polling interval) --.      |          |  yyyy = measured offset,
 ||                                \     |          |  zzzz = estimated error.
 ||                                 |    |           \
 MS Name/IP address         Stratum Poll Reach LastRx Last sample
 ===============================================================================
 ^* 169.254.169.123               2   6   377    34   +89ns[+134ns] +/- 2345us
```

### Key Metrics to Alert On

| Metric | Warning | Critical |
|--------|---------|----------|
| Clock offset | > 10 ms | > 100 ms |
| Root dispersion | > 50 ms | > 500 ms |
| Stratum | > 4 | > 6 or 16 |
| NTP reach | < 377 (octal) | = 0 |
| Poll interval | > 1024s | stuck |

### Leap Seconds

```
  Problem: UTC occasionally adds a leap second (23:59:60)
  
  Option 1: Step (traditional)
    23:59:59 → 23:59:60 → 00:00:00
    Risk: Duplicate timestamps, confused software
    
  Option 2: Smear (Google, AWS, Meta approach)
    Spread 1 second over 24 hours
    Each second is slightly longer (by ~11.6 μs)
    No discontinuity visible to applications
    
  DANGER: Mixing smeared and non-smeared sources = errors!
```

### VM Clock Drift

```
  ┌─────────────────────────────────────┐
  │ Hypervisor                          │
  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │
  │  │ VM1 │ │ VM2 │ │ VM3 │ │ VM4 │  │
  │  │     │ │     │ │     │ │     │  │
  │  │clock│ │clock│ │clock│ │clock│  │
  │  │drifts│ │ok  │ │STOLEN│ │ok  │  │
  │  └─────┘ └─────┘ └──┬──┘ └─────┘  │
  │                      │              │
  │  Stolen time: VM3 was preempted     │
  │  for 500ms, its TSC counter froze   │
  │  → clock jumped 500ms into past     │
  │  relative to real time              │
  └─────────────────────────────────────┘
  
  Mitigations:
  - Use kvm-clock / Hyper-V TSC page (paravirtualized clock)
  - Frequent NTP sync (chrony handles this well)
  - Monitor /proc/stat steal time
```

---

## 13. Architect's Guide

### Design Patterns That Minimize Clock Dependency

```
  ┌─────────────────────────────────────────────────────────────┐
  │              CLOCK DEPENDENCY SPECTRUM                       │
  │                                                             │
  │  SAFE                                              RISKY    │
  │  ◄──────────────────────────────────────────────────────►   │
  │                                                             │
  │  Logical    HLC     Bounded     NTP-based    Client         │
  │  clocks   clocks    intervals   timestamps   timestamps     │
  │  (Lamport) (Cockroach) (TrueTime) (server)   (Cassandra)   │
  │                                                             │
  │  No clock  Physical   Known       Assumed     Unknown       │
  │  needed    + causal   uncertainty  ~10ms      skew          │
  └─────────────────────────────────────────────────────────────┘
```

### Decision Framework

**Q: Do you need real-time ordering across nodes?**
- No → Use logical clocks (cheapest, correct)
- Yes, within bounded latency → HLC or bounded-skew assumption
- Yes, strict external consistency → TrueTime or equivalent (expensive)

**Q: What happens if clocks are wrong?**
- Safety violation (data loss, split-brain) → You MUST handle uncertainty
- Liveness issue (delayed timeout) → Probably acceptable
- Cosmetic (log ordering) → NTP is sufficient

### Key Design Rules

1. **Never trust cross-machine timestamp ordering** unless you've bounded the uncertainty
2. **Use monotonic clocks for durations** (timeouts, rate limiting, SLAs)
3. **Assign timestamps at one place** when possible (single-writer, or leader assigns)
4. **Make clock skew visible** — expose uncertainty, don't hide it
5. **Design for clock failure** — what happens if NTP dies for an hour?
6. **Fencing tokens over timestamps** for distributed locks
7. **Prefer causal ordering** over wall-clock ordering where possible
8. **Server-side timestamps** over client-side (you control the server's clock)

### Handling Uncertainty in Practice

```
  Pattern: "Wait Out Uncertainty" (Spanner-style)
  ─────────────────────────────────────────────────
  Cost: latency (2ε per commit)
  Benefit: true external consistency
  When: strong consistency required, can tolerate ms latency
  
  Pattern: "Restart on Uncertainty" (CockroachDB-style)
  ─────────────────────────────────────────────────
  Cost: occasional transaction restarts
  Benefit: serializable without specialized hardware
  When: NTP-only environments, can retry transactions
  
  Pattern: "Accept and Repair" (Cassandra-style)
  ─────────────────────────────────────────────────
  Cost: potential data loss / inconsistency windows
  Benefit: always available, no coordination
  When: availability > consistency, conflicts rare/resolvable
  
  Pattern: "Single Timestamp Authority"
  ─────────────────────────────────────────────────
  Cost: single point of failure / bottleneck
  Benefit: no cross-machine ordering issues
  When: can afford the bottleneck (TSO in TiDB, sequencer pattern)
```

### Summary: When to Use What

```
  ┌──────────────────────────┬──────────────────────────────────┐
  │ Scenario                 │ Recommendation                   │
  ├──────────────────────────┼──────────────────────────────────┤
  │ Measuring elapsed time   │ Monotonic clock (never wall)     │
  │ Timeout / deadline       │ Monotonic clock + skew budget    │
  │ Distributed lock/lease   │ Fencing token, not timestamp     │
  │ Event ordering (causal)  │ Logical / Vector / HLC           │
  │ Event ordering (real)    │ TrueTime / PTP / bounded NTP    │
  │ TTL / Expiry             │ Server-side clock + buffer       │
  │ Audit / compliance       │ PTP + GPS (provable accuracy)    │
  │ Log correlation          │ NTP + structured trace IDs       │
  │ LWW conflict resolution  │ HLC (not raw wall clock)         │
  │ Global transactions      │ TrueTime or HLC + max-offset    │
  └──────────────────────────┴──────────────────────────────────┘
```

---

## References

- Corbett et al., "Spanner: Google's Globally-Distributed Database" (2012)
- Kulkarni et al., "Logical Physical Clocks and Consistent Snapshots" (HLC paper, 2014)
- Mills, "Network Time Protocol (Version 4)" RFC 5905
- IEEE 1588-2019, "Precision Time Protocol"
- Amazon, "ClockBound: Generating and Verifying Bounded Timestamps"
- Lamport, "Time, Clocks, and the Ordering of Events in a Distributed System" (1978)
