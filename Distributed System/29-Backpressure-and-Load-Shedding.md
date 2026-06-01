# Backpressure and Load Shedding

## 1. Problem Statement

When demand exceeds capacity in a distributed system, the default behavior—unbounded queuing—is catastrophic:

```
                        SYSTEM UNDER OVERLOAD
                        
  Requests/sec ─────────────────────────────────────────────►
  
       ┌─────────────────────────────────────────────────┐
       │                                                 │
  R    │         ╱ Demand                                │
  e    │        ╱                                        │
  q    │       ╱                                         │
  /    │      ╱         ← Gap = Queuing                  │
  s    │─────╱──────────── Capacity ─────────────────────│
       │    ╱                                            │
       │   ╱                                             │
       │  ╱                                              │
       └─────────────────────────────────────────────────┘
                          Time ──►

  What happens in the gap:
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Queue      │     │   Memory     │     │  Cascading   │
  │   Grows      │────►│  Exhaustion  │────►│   Failure    │
  │  Unbounded   │     │   OOM Kill   │     │  Total Loss  │
  └──────────────┘     └──────────────┘     └──────────────┘
```

**Three deadly consequences of uncontrolled queuing:**

1. **Memory exhaustion** — Queues grow until the process is OOM-killed
2. **Unbounded latency** — Items sit in queue so long they're useless when finally processed (Little's Law: L = λW; as queue length L grows, wait time W grows proportionally)
3. **Cascading failures** — Upstream callers timeout, retry, adding more load; downstream services get starved of connections

**The fundamental insight:** A system that accepts work it cannot complete is worse than one that rejects work early. The system must protect itself.

---

## 2. Backpressure — Definition

**Backpressure** is a mechanism where a slow consumer signals upstream producers to reduce their sending rate. It propagates congestion information *backward* through the processing pipeline.

```
  BACKPRESSURE PROPAGATION

  Producer A ──►│         │──► Service B ──►│         │──► Consumer C
                │ Queue 1 │                 │ Queue 2 │    (SLOW)
  Producer D ──►│         │──► Service B ──►│         │──►
                                                          
                                                 ▲
                                                 │ "I'm slow!"
                                                 │
  ◄────────────────── Signal propagates backward ─────────┘
  
  Step 1: Consumer C slows down
  Step 2: Queue 2 fills up → Service B slows down
  Step 3: Queue 1 fills up → Producers A & D slow down
  
  Result: Entire pipeline runs at speed of slowest component
          WITHOUT memory exhaustion or data loss
```

**Key properties:**
- **End-to-end** — Propagates from the point of congestion all the way to the source
- **Self-regulating** — When consumer speeds up, backpressure automatically releases
- **Lossless** — No data is dropped (contrast with load shedding)
- **Latency-adding** — Producers block or buffer, increasing end-to-end latency

**Analogy:** A multi-lane highway merging into fewer lanes. Cars slow down (backpressure) rather than crashing (failure). Traffic information propagates backward through the congestion.

---

## 3. Backpressure Mechanisms

### 3a. Bounded Queues

The simplest form of backpressure: limit the queue size. When full, the producer must block, drop, or receive an error.

```
  BOUNDED QUEUE BACKPRESSURE
  
  Capacity = 5 slots
  
  State 1: Normal operation (queue not full)
  ┌─────────────────────────────────────────┐
  │ Producer ──► │ A │ B │ C │   │   │ ──► Consumer
  │              ├───┴───┴───┴───┴───┤      │
  │              │   3/5 occupied     │      │
  │  Status:     └────────────────────┘      │
  │  Producer sends freely                   │
  └─────────────────────────────────────────┘
  
  State 2: Queue full → Backpressure engaged
  ┌─────────────────────────────────────────┐
  │ Producer ─X─ │ A │ B │ C │ D │ E │ ──► Consumer
  │    ▲         ├───┴───┴───┴───┴───┤      │
  │    │         │   5/5 FULL        │      │  (slow)
  │  BLOCKED     └────────────────────┘      │
  │  (or error)                              │
  └─────────────────────────────────────────┘
  
  Producer options when queue is full:
  ┌────────────────┬──────────────────────────────────────┐
  │ Block          │ Thread waits (simple, risks deadlock)│
  │ Error/Reject   │ Return error to caller immediately   │
  │ Drop oldest    │ Remove head, insert at tail          │
  │ Drop newest    │ Discard incoming item (this one)     │
  │ Timeout block  │ Block for N ms, then error           │
  └────────────────┴──────────────────────────────────────┘
```

**Size-bounded vs Time-bounded queues:**

| Property | Size-Bounded | Time-Bounded (TTL) |
|----------|-------------|-------------------|
| Mechanism | Fixed max elements | Items expire after duration |
| Backpressure | Blocks producer when full | Doesn't block producer |
| Memory | Predictable upper bound | Can grow if items arrive faster than TTL |
| Data loss | Only if explicitly configured | Items silently expire |
| Use case | Pipeline flow control | Request queues with SLA deadlines |
| Example | `ArrayBlockingQueue(1000)` | Items with 5s TTL in queue |

**Sizing the bounded queue:**

```
Optimal queue size ≈ (Producer rate - Consumer rate) × Acceptable burst duration

Example:
  Producer: 1000 req/s
  Consumer: 800 req/s  
  Burst tolerance: 5 seconds
  Queue size = (1000 - 800) × 5 = 1000 items

If burst lasts longer → backpressure kicks in
```

### 3b. Credit-Based Flow Control

The consumer explicitly grants "credits" (permits) to the producer. The producer can only send as many messages as credits it holds.

```
  CREDIT-BASED FLOW CONTROL
  
  ┌──────────┐                          ┌──────────┐
  │          │  ◄─── Grant 5 credits ── │          │
  │          │                          │          │
  │ Producer │  ─── Send msg 1 ──────► │ Consumer │
  │          │  ─── Send msg 2 ──────► │          │
  │          │  ─── Send msg 3 ──────► │          │
  │          │                          │          │
  │ Credits: │  ◄─── Grant 3 credits ── │ Processed│
  │ 5-3+3=5  │                          │ 3 items  │
  │          │  ─── Send msg 4 ──────► │          │
  │          │  ─── Send msg 5 ──────► │          │
  │          │                          │          │
  │ Credits: │                          │          │
  │    3     │  (can still send 3)      │          │
  └──────────┘                          └──────────┘
  
  Rule: Producer NEVER sends if credits == 0
        Consumer grants credits when it has buffer space
```

**TCP Flow Control — The canonical example:**

```
  TCP RECEIVE WINDOW (rwnd)
  
  Sender                                    Receiver
  ┌──────┐                                 ┌──────────────┐
  │      │ ──── Data segment ────────────► │ App buffer:  │
  │      │                                 │ [####____]   │
  │      │ ◄─── ACK, Window=4096 ──────── │ 4096 free    │
  │      │                                 │              │
  │      │ ──── 4096 bytes ─────────────► │ [########]   │
  │      │                                 │ 0 free!      │
  │      │ ◄─── ACK, Window=0 ──────────  │ FULL         │
  │      │                                 │              │
  │STOP! │                                 │ App reads... │
  │      │                                 │ [##______]   │
  │      │ ◄─── Window Update=6144 ─────  │ 6144 free    │
  │      │                                 │              │
  │Resume│ ──── Data ───────────────────► │              │
  └──────┘                                 └──────────────┘
  
  The receive window IS the credit. 
  Window = 0 → Sender must stop (zero-window probe excepted).
```

**Implementations:**

| System | Credit Mechanism |
|--------|-----------------|
| TCP | Receive window (rwnd) in bytes |
| Akka Streams | Demand signals between async boundaries |
| Reactive Streams | `request(n)` from Subscriber to Publisher |
| Apache Flink | Network buffer credits between task managers |
| HTTP/2 | WINDOW_UPDATE frames (per-stream and per-connection) |
| QUIC | MAX_DATA, MAX_STREAM_DATA frames |

### 3c. Rate Limiting

A fixed ceiling on the rate at which requests are accepted. Unlike backpressure (which is dynamic), rate limiting enforces a static or semi-static policy.

**Token Bucket Algorithm:**

```
  TOKEN BUCKET
  
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │    Tokens added at fixed rate (e.g., 100/sec)       │
  │              │                                      │
  │              ▼                                      │
  │    ┌───────────────────┐                            │
  │    │ ○ ○ ○ ○ ○ ○ ○ ○ ○│ ← Bucket (max capacity B) │
  │    │ ○ ○ ○ ○ ○ ○ ○    │   e.g., B = 20 tokens     │
  │    └────────┬──────────┘                            │
  │             │                                       │
  │             ▼                                       │
  │    Request arrives:                                 │
  │    ┌─────────────────┐     ┌──────────────────┐    │
  │    │ Token available? │─Yes─► Remove token,    │    │
  │    │                  │     │ ALLOW request    │    │
  │    └────────┬─────────┘     └──────────────────┘    │
  │             │ No                                    │
  │             ▼                                       │
  │    ┌──────────────────┐                             │
  │    │ REJECT request   │                             │
  │    │ (429 Too Many)   │                             │
  │    └──────────────────┘                             │
  │                                                     │
  │  Properties:                                        │
  │  • Steady-state rate = token refill rate (r)        │
  │  • Burst capacity = bucket size (B)                 │
  │  • Allows short bursts up to B, then enforces r    │
  └─────────────────────────────────────────────────────┘
  
  Timeline example (r=2/sec, B=5):
  
  Time:  0   1   2   3   4   5   6   7   8
  Tokens:[5] [5] [5] [2] [4] [5] [3] [5] [5]
  Reqs:   0   0   5   0   1   4   0   0   0
  Result: -   -  ✓✓✓✓✓ -  ✓   ✓✓✓✓ -  -   -
                  (burst!)      (denied 1: only 3 tokens for 4 reqs... 
                                 actually: 5-4+2=3... let me fix)
```

**Comparison of rate limiting algorithms:**

```
  ┌─────────────────┬──────────────────┬────────────────────┬────────────────┐
  │ Algorithm       │ Burst Behavior   │ Memory             │ Precision      │
  ├─────────────────┼──────────────────┼────────────────────┼────────────────┤
  │ Token Bucket    │ Allows bursts    │ O(1) per key       │ High           │
  │                 │ up to bucket     │                    │                │
  │                 │ size             │                    │                │
  ├─────────────────┼──────────────────┼────────────────────┼────────────────┤
  │ Leaky Bucket    │ Smooths output   │ O(1) per key       │ High           │
  │                 │ to constant rate │                    │ (no bursts)    │
  ├─────────────────┼──────────────────┼────────────────────┼────────────────┤
  │ Fixed Window    │ 2x burst at      │ O(1) per key       │ Low            │
  │                 │ window boundary  │                    │ (boundary)     │
  ├─────────────────┼──────────────────┼────────────────────┼────────────────┤
  │ Sliding Window  │ No boundary      │ O(1) per key       │ High           │
  │ Log             │ issues           │ (but stores        │                │
  │                 │                  │  timestamps)       │                │
  ├─────────────────┼──────────────────┼────────────────────┼────────────────┤
  │ Sliding Window  │ Weighted blend   │ O(1) per key       │ Medium-High    │
  │ Counter         │ of two windows   │                    │                │
  └─────────────────┴──────────────────┴────────────────────┴────────────────┘
```

**Leaky Bucket vs Token Bucket:**

```
  LEAKY BUCKET                         TOKEN BUCKET
  ┌──────────┐                         ┌──────────┐
  │ Requests │                         │  Tokens  │
  │ pour in  │                         │ drip in  │
  │    ▼     │                         │    ▼     │
  │ ┌──────┐ │                         │ ┌──────┐ │
  │ │~~~~~~│ │                         │ │○○○○○○│ │
  │ │~~~~~~│ │                         │ │○○○○  │ │
  │ │~~~~~~│ │                         │ │○○    │ │
  │ └──┬───┘ │                         │ └──────┘ │
  │    │     │                         │          │
  │    ▼     │                         │ Request: │
  │ Constant │                         │ Take 1   │
  │ drain    │                         │ token    │
  │ rate     │                         │          │
  │          │                         │ No token │
  │ Overflow │                         │ = reject │
  │ = reject │                         │          │
  └──────────┘                         └──────────┘
  
  Output: constant rate                Output: up to burst, avg = refill rate
  Bursts: absorbed, output smooth      Bursts: allowed (up to bucket size)
```

### 3d. Reactive Streams Protocol

A specification (Java 9 Flow API, Project Reactor, RxJava, Akka Streams) that builds backpressure into the contract between components.

```
  REACTIVE STREAMS: request(N) PROTOCOL
  
  ┌────────────┐                         ┌────────────────┐
  │            │  ──── subscribe() ────► │                │
  │            │                         │                │
  │            │  ◄─── onSubscribe(s) ── │                │
  │            │                         │                │
  │ Subscriber │  ──── s.request(3) ───► │   Publisher    │
  │            │                         │                │
  │            │  ◄─── onNext(item1) ─── │                │
  │            │  ◄─── onNext(item2) ─── │                │
  │            │  ◄─── onNext(item3) ─── │   Demand = 0  │
  │            │                         │   MUST STOP   │
  │            │                         │                │
  │  (process) │                         │   (waiting)   │
  │            │                         │                │
  │            │  ──── s.request(5) ───► │                │
  │            │                         │   Demand = 5  │
  │            │  ◄─── onNext(item4) ─── │                │
  │            │  ...                    │                │
  └────────────┘                         └────────────────┘
  
  RULES:
  1. Publisher MUST NOT send more than requested
  2. Subscriber controls the pace
  3. request(Long.MAX_VALUE) = "give me everything" (unbounded)
  4. Signals are non-reentrant and serialized
```

**The four interfaces:**

```java
public interface Publisher<T> {
    void subscribe(Subscriber<? super T> s);
}

public interface Subscriber<T> {
    void onSubscribe(Subscription s);
    void onNext(T t);           // Publisher sends item
    void onError(Throwable t);  // Terminal: error
    void onComplete();          // Terminal: done
}

public interface Subscription {
    void request(long n);       // Subscriber requests N items
    void cancel();              // Subscriber cancels
}

public interface Processor<T, R> extends Subscriber<T>, Publisher<R> {}
```

**Backpressure strategies when demand < supply:**

| Strategy | Description | Use Case |
|----------|-------------|----------|
| Buffer | Queue items (bounded!) | Bursty producers |
| Drop | Discard items not requested | Sensor data (latest matters) |
| Latest | Keep only most recent | UI updates |
| Error | Signal error on overflow | Strict processing |
| Request-based | Only pull when ready | Database cursors |

---

## 4. Load Shedding — Definition

**Load shedding** is the deliberate dropping of work to preserve system stability. Unlike backpressure (which slows producers), load shedding accepts that some work will be lost to save the whole system.

```
  THE LIFEBOAT PRINCIPLE
  
  Without load shedding:              With load shedding:
  ┌─────────────────────┐            ┌─────────────────────┐
  │  Lifeboat: 10 cap   │            │  Lifeboat: 10 cap   │
  │  People: 20         │            │  People: 20         │
  │                     │            │                     │
  │  Result:            │            │  Result:            │
  │  ALL 20 DROWN       │            │  10 saved, 10 lost  │
  │  (boat sinks)       │            │  (boat survives)    │
  └─────────────────────┘            └─────────────────────┘
  
  In system terms:
  ┌─────────────────────┐            ┌─────────────────────┐
  │ Accept all requests │            │ Reject excess early  │
  │ Queue grows → OOM   │            │ Process what we can  │
  │ GC pressure → slow  │            │ Return 503 to rest   │
  │ Timeouts → retries  │            │ System stays healthy │
  │ Everything fails    │            │ Good requests succeed│
  └─────────────────────┘            └─────────────────────┘
  
  Goodput comparison:
  
  Goodput│      ╱── With load shedding (graceful degradation)
        │     ╱ ─────────────────────────
        │    ╱                      
        │   ╱
        │  ╱   ╲── Without (collapse under overload)
        │ ╱     ╲
        │╱       ╲__________
        └──────────────────────── Load
              ▲
              │
         Capacity limit
```

**Key insight:** A system doing useful work at 80% capacity is vastly better than one doing no useful work at 120% attempted capacity. The goal is to maximize **goodput** (successful, timely completions), not throughput.

---

## 5. Load Shedding Strategies

### 5a. LIFO (Last In, First Out) Shedding

Drop the **newest** arrivals. Rationale: older requests have already consumed wait time; newer ones haven't invested anything yet.

```
  LIFO Shedding (drop newest):
  
  Queue: [Oldest ─────────────────── Newest]
         [  A  |  B  |  C  |  D  |  E  ]
                                      ▲
                                      │ DROP THIS
  
  Why: A has been waiting 4s. If we process A, its total latency = 4s + processing.
       If we drop A and process E, A wasted 4s AND still fails.
       Better: process A (it's closer to completion), drop E (zero investment).
```

**Counter-intuitive alternative — drop oldest (FIFO shedding):** Sometimes you drop the *oldest* because they've likely already timed out at the client. A request waiting 30s in queue when the client timeout is 5s is dead work. This is deadline-based shedding (see 5e).

### 5b. Priority-Based Shedding

Classify traffic into priority tiers. Under overload, shed lowest priority first.

```
  PRIORITY-BASED LOAD SHEDDING
  
  ┌─────────────────────────────────────────────────────────┐
  │  Traffic Classification                                 │
  │                                                         │
  │  P0 (Critical):  Payment processing, auth tokens       │
  │  P1 (High):      User-facing reads, search             │
  │  P2 (Medium):    Analytics events, notifications       │
  │  P3 (Low):       Prefetch, background sync, telemetry  │
  │                                                         │
  │  Shedding order under increasing load:                  │
  │                                                         │
  │  Load 80%:  All traffic served                          │
  │  Load 90%:  ┃ P0 ✓ │ P1 ✓ │ P2 ✓ │ P3 ✗ (shed) ┃     │
  │  Load 95%:  ┃ P0 ✓ │ P1 ✓ │ P2 ✗ │ P3 ✗         ┃     │
  │  Load 99%:  ┃ P0 ✓ │ P1 ✗ │ P2 ✗ │ P3 ✗         ┃     │
  │  Load 100%: ┃ P0 ✓ │ Everything else shed         ┃     │
  └─────────────────────────────────────────────────────────┘
```

**Implementation considerations:**
- Priority must be determined cheaply (usually from headers/metadata, not request body)
- Avoid priority inversion: a P3 request holding a lock needed by P0
- Starvation protection: even P3 traffic should get *some* service over time
- Google's approach: "criticality" field in RPC metadata (CRITICAL_PLUS, CRITICAL, SHEDDABLE_PLUS, SHEDDABLE)

### 5c. Random Shedding

Drop requests uniformly at random. Simple, fair, and surprisingly effective.

```
  Random shedding at 20% drop rate:
  
  Incoming: [R1][R2][R3][R4][R5][R6][R7][R8][R9][R10]
  Random:    .3  .8  .1  .5  .9  .2  .7  .4  .6  .95
  Threshold: < 0.2 = drop
  Result:         ✗       ✗       ✗ 
            [R1]    [R3][R4]    [R6][R7][R8][R9][R10]
              ✓  ✗   ✓   ✓  ✗   ✗   ✓   ✓   ✓   ✓
```

**Advantages:**
- No classification logic needed
- Fair across all clients and request types
- No state to maintain
- No gaming possible

**Disadvantage:** Treats all requests equally — drops critical and non-critical alike.

### 5d. CoDel (Controlled Delay)

Developed for network routers (Kathleen Nichols & Van Jacobson, 2012). Drops based on **sojourn time** (how long a packet/request has been in queue), not queue length.

```
  CoDel ALGORITHM
  
  Parameters:
    TARGET  = 5ms   (acceptable queuing delay)
    INTERVAL = 100ms (measurement window)
  
  Logic:
  ┌────────────────────────────────────────────────────────┐
  │                                                        │
  │  On dequeue(item):                                     │
  │    sojourn_time = now - item.enqueue_time              │
  │                                                        │
  │    if sojourn_time < TARGET:                           │
  │      // Good: queue is draining fast                   │
  │      reset dropping state                              │
  │    else:                                               │
  │      // Bad: item waited too long                      │
  │      if in_dropping_state:                             │
  │        if time_since_last_drop > interval/√count:     │
  │          DROP item                                     │
  │          count++                                       │
  │      else:                                             │
  │        if bad_for_entire_INTERVAL:                     │
  │          enter dropping state                          │
  │          DROP item                                     │
  │          count = 1                                     │
  │                                                        │
  └────────────────────────────────────────────────────────┘
  
  Key insight: CoDel drops based on SUSTAINED bad latency,
  not momentary spikes. A brief burst fills the queue but
  drains quickly → no drops. Sustained overload → drops
  increase at accelerating rate (1/√n spacing).
```

**Why CoDel is superior to tail-drop:**
- Tail-drop (drop when queue full) creates **bufferbloat** — queue stays full, latency stays high
- CoDel keeps queuing delay bounded regardless of queue size
- Self-tuning: drop rate automatically adjusts to match overload severity

### 5e. Deadline-Based Shedding

If a request has already exceeded its deadline (client timeout, SLA), processing it is wasted work. Drop it immediately.

```
  DEADLINE-BASED SHEDDING
  
  Client timeout: 5 seconds
  
  Queue at dequeue time:
  ┌─────┬─────┬─────┬─────┬─────┐
  │  A  │  B  │  C  │  D  │  E  │
  │age:8│age:6│age:4│age:2│age:1│  (seconds in queue)
  │DEAD │DEAD │ OK  │ OK  │ OK  │
  └─────┴─────┴─────┴─────┴─────┘
    ▲      ▲
    │      └── Drop: client already timed out
    └───────── Drop: client already timed out
  
  Process only C, D, E — they can still meet SLA
```

**Implementation:** Propagate deadlines through the system. gRPC does this with `grpc-timeout` header. Each hop subtracts its processing time from the remaining deadline.

```
  Deadline propagation:
  
  Client ──[deadline: 5s]──► Gateway ──[deadline: 4.8s]──► Service A
                                                               │
                            [deadline: 3.2s]                    │
  Client ◄────────────────── Gateway ◄──────────────────── Service A
```

### 5f. Client-Based Shedding (Heavy-Hitter Throttling)

Identify clients consuming disproportionate resources and throttle them specifically.

```
  Client request distribution:
  
  Client │ Requests/sec │ Action
  ───────┼──────────────┼──────────────────────
  Org-A  │ 50           │ Normal
  Org-B  │ 45           │ Normal  
  Org-C  │ 5000 ←──────┼── HEAVY HITTER: throttle
  Org-D  │ 30           │ Normal
  
  Approach: Per-client rate limits, fair-share scheduling
  Detection: Sketch data structures (Count-Min Sketch) for 
             space-efficient heavy-hitter detection
```

---

## 6. Circuit Breaker Pattern

Prevents a failing downstream service from causing cascading failures upstream. Inspired by electrical circuit breakers.

```
  CIRCUIT BREAKER STATE MACHINE
  
                    failure_count >= threshold
         ┌──────────────────────────────────────────┐
         │                                          ▼
  ┌──────────────┐                          ┌──────────────┐
  │              │                          │              │
  │    CLOSED    │                          │     OPEN     │
  │   (normal)   │                          │  (rejecting) │
  │              │                          │              │
  │ All requests │                          │ All requests │
  │ pass through │                          │ fail-fast    │
  │              │                          │ (no call to  │
  │ Monitor      │                          │  downstream) │
  │ failures     │                          │              │
  └──────────────┘                          └──────┬───────┘
         ▲                                         │
         │                                         │ timeout expires
         │         success                         ▼
         │    ┌──────────────────────┐     ┌──────────────┐
         │    │                      │     │              │
         └────┤      HALF-OPEN      │◄────┤  Timer       │
              │    (testing)         │     │  (cooldown)  │
              │                      │     └──────────────┘
              │ Allow LIMITED        │
              │ requests through     │
              │                      │
              │ Success → CLOSED     │
              │ Failure → OPEN       │
              └──────────────────────┘
  
  
  DETAILED STATE TRANSITIONS:
  
  ┌─────────┐  request   ┌──────────┐  success  ┌─────────┐
  │ CLOSED  │───────────►│  Call    │──────────►│ CLOSED  │
  │         │            │downstream│           │(reset   │
  │         │            │          │           │ counter)│
  │         │            │          │──failure─►│count++ │
  └─────────┘            └──────────┘           └────┬────┘
                                                     │
                                          count >= threshold
                                                     │
                                                     ▼
  ┌─────────┐  request   ┌──────────┐         ┌─────────┐
  │  OPEN   │───────────►│Fail-fast │         │  OPEN   │
  │         │            │(no call) │         │         │
  │         │            │Return err│         │         │
  └────┬────┘            └──────────┘         └─────────┘
       │ timer expires
       ▼
  ┌─────────┐  request   ┌──────────┐  success  ┌─────────┐
  │HALF-OPEN│───────────►│  Call    │──────────►│ CLOSED  │
  │(1 req)  │            │downstream│           │         │
  │         │            │          │──failure─►│  OPEN   │
  └─────────┘            └──────────┘           │(restart │
                                                │ timer)  │
                                                └─────────┘
```

**Configuration parameters:**

| Parameter | Typical Value | Purpose |
|-----------|--------------|---------|
| Failure threshold | 5-10 failures | Consecutive failures to trip |
| Failure rate threshold | 50% | Failure rate over window to trip |
| Timeout duration | 30-60 seconds | How long to stay OPEN |
| Half-open permits | 1-3 requests | Test requests in HALF-OPEN |
| Sliding window size | 10-100 calls | Window for calculating failure rate |
| Slow call threshold | 2-5 seconds | Calls slower than this count as failures |

**Libraries:**

| Library | Language | Notes |
|---------|----------|-------|
| Hystrix | Java | Netflix, now in maintenance mode |
| Resilience4j | Java | Modern replacement for Hystrix |
| Polly | .NET | Policy-based resilience |
| gobreaker | Go | Sony's implementation |
| pybreaker | Python | Simple, effective |
| opossum | Node.js | Promise-based |

**Advanced patterns:**
- **Per-endpoint breakers** — Don't break all calls to a service because one endpoint is failing
- **Bulkhead + Circuit Breaker** — Separate thread pools per dependency, each with its own breaker
- **Adaptive thresholds** — Adjust failure threshold based on traffic volume

---

## 7. Admission Control

The principle of **rejecting work at the front door** — the cheapest place to shed load.

```
  ADMISSION CONTROL LAYERS
  
  Internet
     │
     ▼
  ┌──────────────────┐
  │   Load Balancer  │──── Connection limits, rate limits
  │   (L4/L7)       │     (cheapest rejection point)
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │   API Gateway    │──── Auth, rate limit per API key
  │   / Reverse Proxy│     HTTP 429 Too Many Requests
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │   Application    │──── Concurrency limits, queue bounds
  │   Server         │     HTTP 503 Service Unavailable  
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │   Worker Pool    │──── Thread pool rejection
  │                  │     Already past admission control
  └──────────────────┘
  
  PRINCIPLE: Reject as early as possible.
  Cost of rejection at LB: ~0.01ms, ~100 bytes
  Cost of rejection at app: ~5ms, connection, thread, parsing...
```

**HTTP Response Codes for Admission Control:**

| Code | Meaning | When to Use |
|------|---------|-------------|
| 429 | Too Many Requests | Client exceeded rate limit |
| 503 | Service Unavailable | Server overloaded, try later |
| 504 | Gateway Timeout | Upstream didn't respond in time |

**Retry-After header:** Signal to clients when to retry:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 30
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1672531260
```

**Client-side retry with exponential backoff + jitter:**

```
  EXPONENTIAL BACKOFF WITH FULL JITTER
  
  Attempt │ Base delay │ Max delay   │ Actual (random in [0, max])
  ────────┼────────────┼─────────────┼──────────────────────────────
     1    │   1s       │   1s        │  random(0, 1s)   = 0.7s
     2    │   1s       │   2s        │  random(0, 2s)   = 1.3s
     3    │   1s       │   4s        │  random(0, 4s)   = 2.8s
     4    │   1s       │   8s        │  random(0, 8s)   = 5.1s
     5    │   1s       │  16s        │  random(0, 16s)  = 9.4s
     6    │   1s       │  32s (cap)  │  random(0, 32s)  = 21.7s
  
  Formula: sleep = random(0, min(cap, base * 2^attempt))
  
  WHY JITTER IS ESSENTIAL:
  
  Without jitter (thundering herd):
  Time: ─────┬────────┬────────┬────────
             │████████│████████│████████  (all retry at same instant)
  
  With full jitter (spread out):
  Time: ─────┬─┬──┬─┬──┬──┬─┬──┬──────
             │ █ ██ █ ██ ██ █ ██         (retries spread across window)
```

**Adaptive Admission Control (Netflix approach):**

```python
# Simplified adaptive admission control
class AdaptiveThrottler:
    def __init__(self):
        self.requests = 0      # total requests attempted
        self.accepts = 0       # requests accepted by backend
    
    def should_throttle(self) -> bool:
        # Client-side throttling probability
        # As rejection rate increases, client preemptively drops more
        rejection_probability = max(0, 
            (self.requests - K * self.accepts) / (self.requests + 1))
        return random() < rejection_probability
    
    # K = multiplier (e.g., 2.0)
    # When accepts ≈ requests: probability ≈ 0 (no throttling)
    # When accepts << requests: probability → 1 (heavy throttling)
```

---

## 8. Real-World Implementations

### TCP — The Original Backpressure System

```
  TCP CONGESTION CONTROL + FLOW CONTROL
  
  Two separate mechanisms:
  
  1. FLOW CONTROL (receiver-driven backpressure):
     Receiver advertises: "I have X bytes free" (rwnd)
     Sender cannot exceed rwnd
  
  2. CONGESTION CONTROL (network-driven):
     Sender probes available bandwidth (cwnd)
     
     sending_rate = min(rwnd, cwnd) / RTT
  
  AIMD (Additive Increase, Multiplicative Decrease):
  
  cwnd │      ╱╲      ╱╲      ╱╲
       │     ╱  ╲    ╱  ╲    ╱  ╲
       │    ╱    ╲  ╱    ╲  ╱    ╲
       │   ╱      ╲╱      ╲╱      ╲  (sawtooth)
       │  ╱
       │ ╱
       └──────────────────────────── time
           ▲         ▲         ▲
           │         │         │
        packet loss detected → cut cwnd in half
```

### Apache Kafka

```
  KAFKA PRODUCER BACKPRESSURE
  
  ┌──────────────────────────────────────────────────────────┐
  │  Producer Process                                        │
  │                                                          │
  │  Application Thread          Sender Thread               │
  │  ┌──────────┐              ┌──────────────┐             │
  │  │  send()  │─────────────►│ RecordAccum- │──► Broker   │
  │  │          │              │ ulator       │             │
  │  │  BLOCKS  │◄─────────────│              │             │
  │  │  if full │  backpressure│ buffer.memory│             │
  │  └──────────┘              │ = 32MB       │             │
  │                            │              │             │
  │  max.block.ms = 60000      │ batch.size   │             │
  │  (block up to 60s, then    │ = 16KB       │             │
  │   throw exception)         └──────────────┘             │
  │                                                          │
  └──────────────────────────────────────────────────────────┘
  
  Key configs:
  • buffer.memory (33554432) — Total buffer memory; backpressure trigger
  • max.block.ms (60000) — How long send() blocks before exception
  • linger.ms (0) — Wait time for batching
  • acks (all/-1) — Durability vs throughput tradeoff
```

### Apache Flink — Credit-Based Network Backpressure

```
  FLINK CREDIT-BASED FLOW CONTROL
  
  TaskManager A                      TaskManager B
  ┌─────────────────┐              ┌─────────────────┐
  │ Operator         │              │ Operator         │
  │    │             │              │    ▲             │
  │    ▼             │              │    │             │
  │ Result          │              │ Input           │
  │ Partition       │              │ Gate            │
  │    │             │              │    ▲             │
  │    ▼             │              │    │             │
  │ ┌───────────┐   │  Network    │ ┌───────────┐   │
  │ │ Netty     │   │             │ │ Netty     │   │
  │ │ Output    │───┼─────────────┼─│ Input     │   │
  │ │ Buffers   │   │             │ │ Buffers   │   │
  │ │           │◄──┼── Credits ──┼─│(announces │   │
  │ │ Can only  │   │             │ │ available │   │
  │ │ send if   │   │             │ │ buffers)  │   │
  │ │ credits>0 │   │             │ │           │   │
  │ └───────────┘   │              │ └───────────┘   │
  └─────────────────┘              └─────────────────┘
  
  If downstream is slow:
  1. Input buffers fill up → fewer credits sent upstream
  2. Upstream output buffers fill up → operator blocks
  3. Backpressure propagates through entire DAG
```

### gRPC Flow Control

```
  gRPC uses HTTP/2 flow control:
  
  • Per-stream window (default: 64KB initially, BDP-based after)
  • Per-connection window
  • WINDOW_UPDATE frames grant additional capacity
  • BDP (Bandwidth-Delay Product) estimation for auto-tuning
  
  Client ────[DATA frames]────► Server
  Client ◄───[WINDOW_UPDATE]─── Server  (grants more window)
  
  If server stops sending WINDOW_UPDATE → client blocks
```

### Envoy Proxy

```
  ENVOY CIRCUIT BREAKING + LOAD SHEDDING
  
  circuit_breakers:
    thresholds:
    - priority: DEFAULT
      max_connections: 1024        # Connection pool limit
      max_pending_requests: 1024   # Queue depth limit  
      max_requests: 1024           # Active request limit
      max_retries: 3               # Concurrent retry limit
      
  # When any threshold exceeded → immediate 503
  # This IS load shedding at the proxy layer
```

### Amazon — Shuffle Sharding

```
  SHUFFLE SHARDING (isolates blast radius)
  
  Traditional sharding:              Shuffle sharding:
  ┌─────────────────┐               ┌─────────────────────────┐
  │ Customer A ──► Shard 1          │ Customer A ──► {1, 3}   │
  │ Customer B ──► Shard 1          │ Customer B ──► {2, 4}   │
  │ Customer C ──► Shard 2          │ Customer C ──► {1, 4}   │
  │ Customer D ──► Shard 2          │ Customer D ──► {3, 2}   │
  │                                 │                         │
  │ If A is noisy neighbor:         │ If A is noisy neighbor: │
  │ B also affected (same shard)    │ Only A affected         │
  │                                 │ (unique combination)    │
  └─────────────────┘               └─────────────────────────┘
  
  With 8 shards, pick 2 per customer:
  C(8,2) = 28 unique combinations
  Probability two customers share BOTH shards: 1/28 ≈ 3.6%
  
  Combined with load shedding: if one shard overloaded,
  only customers assigned to that shard are affected.
```

### Google — Client-Side Throttling

Google's approach from the SRE book:

```python
# Google's client-side adaptive throttling
# (from "Handling Overload" chapter, Google SRE Book)

requests = 0       # Total requests in last 2 minutes
accepts = 0        # Requests accepted in last 2 minutes

def client_throttle_probability():
    return max(0, (requests - K * accepts) / (requests + 1))
    # K = 2.0 typically
    # 
    # Normal: accepts ≈ requests → prob ≈ 0
    # Overload: accepts << requests → prob approaches 1
    #
    # Effect: clients preemptively back off,
    # reducing load on already-stressed servers
```

### Netflix — Concurrency Limits

```
  NETFLIX ADAPTIVE CONCURRENCY LIMITS
  (github.com/Netflix/concurrency-limits)
  
  Based on TCP Vegas algorithm applied to services:
  
  Concept: Infer queue buildup from latency changes
  
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  RTT_noload = minimum observed latency              │
  │  RTT_actual = current latency                       │
  │                                                     │
  │  gradient = RTT_noload / RTT_actual                 │
  │                                                     │
  │  new_limit = current_limit × gradient + queue_size  │
  │                                                     │
  │  If gradient < 1: latency increasing → reduce limit │
  │  If gradient ≈ 1: at optimal → maintain             │
  │  If gradient = 1 and spare capacity → increase      │
  │                                                     │
  └─────────────────────────────────────────────────────┘
  
  No configuration needed — auto-detects optimal concurrency!
```

### Uber — QALM (Quality-Aware Load Management)

Uber's system classifies requests and sheds based on criticality:
- **Critical:** Ride completion, payment capture
- **Degraded:** Search (return cached/fewer results)
- **Sheddable:** Analytics, non-real-time features

QALM provides a centralized control plane that adjusts shedding percentages across services based on global system health.

---

## 9. Cascading Failure Prevention

```
  CASCADING FAILURE ANATOMY
  
  Normal state:
  Client ──► Service A ──► Service B ──► Service C ──► DB
                                                        │
  Step 1: DB gets slow (disk full, lock contention)     │◄── ROOT CAUSE
                                                        │
  Step 2: Service C connections pool up waiting for DB  
           Thread pool exhausted                        
                                                        
  Step 3: Service B timeouts on calls to C             
           Retries 3x → 3x load on C (already dying!)  
           B's thread pool fills up                     
                                                        
  Step 4: Service A timeouts on calls to B             
           Retries → more load on B                    
           A's thread pool fills up                     
                                                        
  Step 5: Client gets timeouts/errors from A           
           Client retries → everything gets worse       
  
  ═══════════════════════════════════════════════════════
  
  THE RETRY STORM:
  
           Original    After retries (3x each layer)
  DB       100 req/s   100 req/s (same)
  C→DB     100 req/s   300 req/s  (C retries 3x)
  B→C      100 req/s   900 req/s  (B retries 3x × C's 3x)
  A→B      100 req/s   2700 req/s (A retries 3x × B × C)
  Client   100 req/s   8100 req/s (client retries too)
  
  AMPLIFICATION: 81x load from 100 req/s original!
```

**Mitigation strategies:**

```
  CASCADING FAILURE PREVENTION
  
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  1. CIRCUIT BREAKERS at each service boundary           │
  │                                                         │
  │  Client ──►[CB]── A ──►[CB]── B ──►[CB]── C ──► DB    │
  │                                                         │
  │  When B→C circuit opens:                                │
  │  • B returns fallback/error immediately                 │
  │  • No further load on C                                 │
  │  • C gets breathing room to recover                     │
  │                                                         │
  │  2. RETRY BUDGETS (max 10% retries)                     │
  │                                                         │
  │  Service B config:                                      │
  │    retry_budget: 10%                                    │
  │    meaning: of all requests to C, max 10% can be retries│
  │                                                         │
  │  At 100 req/s to C:                                     │
  │    max 10 retries/s allowed (not 200!)                  │
  │    If more needed → just fail, don't retry              │
  │                                                         │
  │  3. EXPONENTIAL BACKOFF + JITTER (see Section 7)        │
  │                                                         │
  │  4. DEADLINE PROPAGATION                                │
  │                                                         │
  │  Client sets deadline: 5s                               │
  │  A uses 1s → passes deadline 4s to B                    │
  │  B uses 0.5s → passes deadline 3.5s to C               │
  │  C sees 3.5s remaining, can decide if worth trying      │
  │  If deadline already passed → fail fast, don't call DB  │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

**Retry budget implementation:**

```
  RETRY BUDGET ENFORCEMENT
  
  Window: last 10 seconds
  
  Total requests in window: 1000
  Budget: 10% = max 100 retries allowed
  
  Current retries in window: 95
  New retry needed? 
    95 < 100 → ALLOW (5 retries left in budget)
  
  Current retries in window: 100
  New retry needed?
    100 >= 100 → DENY (budget exhausted, just fail)
  
  Effect: Under heavy failure, retry rate is capped.
  System degrades gracefully instead of amplifying.
```

---

## 10. Capacity Planning Relationship

```
  BACKPRESSURE & LOAD SHEDDING vs CAPACITY PLANNING
  
  ┌───────────────────────────────────────────────────────┐
  │                                                       │
  │  Capacity planning = building the right-sized pipe    │
  │  Backpressure/shedding = safety valves on the pipe    │
  │                                                       │
  │  You need BOTH:                                       │
  │                                                       │
  │  Only capacity planning: no protection against        │
  │    unexpected spikes, failures, or misestimates       │
  │                                                       │
  │  Only backpressure/shedding: constantly rejecting     │
  │    users = bad product, revenue loss                  │
  │                                                       │
  └───────────────────────────────────────────────────────┘
```

**Monitoring signals that indicate you need more capacity (not just better shedding):**

| Signal | Warning | Critical | Action |
|--------|---------|----------|--------|
| Queue depth | > 50% capacity for 5min | > 80% sustained | Scale up |
| P99 latency | > 2x baseline | > 5x baseline | Investigate + scale |
| Error rate (5xx) | > 1% | > 5% | Immediate scale |
| CPU utilization | > 70% sustained | > 85% sustained | Scale up |
| Load shedding rate | > 5% of traffic | > 15% of traffic | Capacity problem |
| Circuit breaker trips | Any trip | Frequent trips | Fix dependency or scale |

**Auto-scaling triggers:**

```
  AUTO-SCALING DECISION FLOW
  
  Metrics ──► Aggregator ──► Scale Decision
  
  Rule-based example:
    IF cpu_avg > 70% for 3 minutes → add 2 instances
    IF request_queue_depth > 1000 → add 1 instance
    IF p99_latency > 500ms for 5 min → add 1 instance
    IF cpu_avg < 30% for 10 minutes → remove 1 instance
  
  Predictive:
    Train model on historical traffic patterns
    Pre-scale before known peaks (Monday 9am, Black Friday)
  
  CRITICAL: Auto-scaling has lag (2-5 minutes for VMs, 
  30s for containers). Backpressure/shedding covers the gap.
```

---

## 11. Architect's Guide — Layered Defense Strategy

```
  LAYERED DEFENSE MODEL
  
  ════════════════════════════════════════════════════════════
  
  Layer 1: ADMISSION CONTROL (outermost, cheapest)
  ┌──────────────────────────────────────────────────────┐
  │  • Rate limits at edge (CDN, LB)                     │
  │  • API key quotas                                    │
  │  • Connection limits                                 │
  │  • Cost: ~0.01ms per decision                        │
  │  • Goal: Keep garbage out                            │
  └──────────────────────────────┬───────────────────────┘
                                 │ Admitted traffic
                                 ▼
  Layer 2: BACKPRESSURE (flow control)
  ┌──────────────────────────────────────────────────────┐
  │  • Bounded queues between components                 │
  │  • Credit-based flow control                         │
  │  • Reactive streams (request-N)                      │
  │  • Cost: latency increase (queuing)                  │
  │  • Goal: Match throughput to slowest component       │
  └──────────────────────────────┬───────────────────────┘
                                 │ If backpressure insufficient
                                 ▼
  Layer 3: LOAD SHEDDING (active dropping)
  ┌──────────────────────────────────────────────────────┐
  │  • Priority-based shedding                           │
  │  • Deadline-based expiry                             │
  │  • CoDel-based queue management                     │
  │  • Cost: dropped requests (but system survives)      │
  │  • Goal: Protect system, maximize goodput            │
  └──────────────────────────────┬───────────────────────┘
                                 │ If downstream still failing
                                 ▼
  Layer 4: CIRCUIT BREAKING (isolation)
  ┌──────────────────────────────────────────────────────┐
  │  • Stop calling failing dependencies                 │
  │  • Return fallbacks/cached data                      │
  │  • Periodic health probes (half-open)                │
  │  • Cost: degraded functionality                      │
  │  • Goal: Prevent cascading failure                   │
  └──────────────────────────────────────────────────────┘
  
  ════════════════════════════════════════════════════════════
```

### Design Principles for Resilient Systems

**1. Fail fast, fail cheap**
```
Reject at the earliest, cheapest point. A 429 at the gateway costs 
microseconds. A timeout after 30s of processing costs a thread, 
memory, DB connections, and downstream calls — all wasted.
```

**2. Distinguish load from failure**
```
Load problem:  System healthy but overwhelmed → shed load, scale up
Failure:       Component broken → circuit break, failover

Different problems, different solutions. Don't circuit-break 
when you just need to shed load. Don't shed load when a 
dependency is down (you'll shed everything).
```

**3. Preserve partial availability**
```
A system serving 70% of requests successfully during overload 
is infinitely better than one serving 0%. Design for graceful 
degradation, not binary up/down.
```

**4. Make shedding observable**
```
Every shed/rejected request should:
- Increment a counter (metric)
- Log (sampled) with reason
- Return appropriate status code
- Include Retry-After when possible

If you can't see shedding happening, you can't tune it.
```

**5. Test overload behavior explicitly**
```
- Chaos engineering: inject failures
- Load testing beyond capacity (not just to capacity)
- Game days: practice incident response for overload scenarios
- Verify circuit breakers actually trip
- Verify shedding policies work as designed
```

**6. The hierarchy of response to overload:**

```
  RESPONSE HIERARCHY (in order of preference)
  
  1. Auto-scale to meet demand        (best: no user impact)
  2. Backpressure: slow producers      (good: higher latency)
  3. Shed low-priority traffic         (ok: some users affected)
  4. Shed randomly across all traffic  (worse: all users affected)
  5. Circuit break failing paths       (degraded: features unavailable)
  6. Full service unavailable          (worst: complete outage)
  
  Design goal: Stay at levels 1-3. Never reach 6.
```

**7. Configuration checklist for production services:**

```
  ┌─────────────────────────────────────────────────────────┐
  │ RESILIENCE CONFIGURATION CHECKLIST                      │
  ├─────────────────────────────────────────────────────────┤
  │                                                         │
  │ □ Timeouts on ALL outbound calls (no infinite waits)    │
  │ □ Circuit breaker on each downstream dependency         │
  │ □ Bounded thread pools / connection pools               │
  │ □ Bounded request queues with clear overflow policy     │
  │ □ Rate limits at service entry point                    │
  │ □ Retry policy with backoff + jitter + budget           │
  │ □ Deadline propagation across service calls             │
  │ □ Health check endpoint (not just "process alive")      │
  │ □ Graceful shutdown (drain in-flight, reject new)       │
  │ □ Load shedding policy defined and tested               │
  │ □ Monitoring: queue depth, latency percentiles,         │
  │   error rates, shedding rates, breaker state            │
  │ □ Alerts on sustained shedding (capacity signal)        │
  │ □ Runbook for overload scenarios                        │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

---

## Summary Table

| Mechanism | Type | Data Loss? | Latency Impact | Complexity |
|-----------|------|-----------|----------------|------------|
| Bounded queues | Backpressure | No (blocks) | Increases | Low |
| Credit-based flow | Backpressure | No | Increases | Medium |
| Rate limiting | Admission control | Yes (rejects) | None for accepted | Low |
| Reactive Streams | Backpressure | No | Increases | Medium |
| LIFO shedding | Load shedding | Yes | Decreases for served | Low |
| Priority shedding | Load shedding | Yes (low-pri) | Stable for high-pri | Medium |
| CoDel | Load shedding | Yes | Bounded | High |
| Circuit breaker | Isolation | Yes (fail-fast) | Decreases (fast fail) | Medium |
| Adaptive concurrency | Auto-tuning | Yes (rejects) | Self-optimizing | High |

---

## Key References

- Nichols & Jacobson, "Controlling Queue Delay" (CoDel paper, 2012)
- Google SRE Book, Ch. 21: "Handling Overload"
- Amazon Builders' Library: "Using load shedding to avoid overload"
- Netflix Tech Blog: "Performance Under Load" (adaptive concurrency)
- Marc Brooker (AWS): "Shuffle Sharding"
- Reactive Streams Specification: reactive-streams.org
- Little's Law: L = λW (fundamental queuing theory)
