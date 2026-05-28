# Redis Locking & Distributed Locks — Production Deep Dive

## Table of Contents
- [Why Distributed Locks](#why-distributed-locks)
- [SETNX — Legacy Pattern](#setnx--legacy-pattern)
- [SET NX EX — Modern Atomic Lock](#set-nx-ex--modern-atomic-lock)
- [Lock Release with Lua Scripts](#lock-release-with-lua-scripts)
- [Watchdog / TTL Renewal](#watchdog--ttl-renewal)
- [Redlock Algorithm](#redlock-algorithm)
- [Fencing Tokens](#fencing-tokens)
- [Lease-Based Leader Election](#lease-based-leader-election)
- [Production Pitfalls](#production-pitfalls)
- [Multi-Language Implementations](#multi-language-implementations)
- [Observability & Monitoring](#observability--monitoring)

---

## Why Distributed Locks

In distributed systems, multiple processes across different machines need mutual exclusion to:
- Prevent double-processing of jobs (payment deduction, inventory decrement)
- Coordinate leader election (only one scheduler runs cron jobs)
- Serialize access to shared external resources (API rate limits, file systems)
- Prevent race conditions in read-modify-write cycles

Redis is popular for distributed locking because:
1. Single-threaded command execution — no internal race conditions
2. Sub-millisecond latency — minimal lock acquisition overhead
3. Built-in TTL — automatic deadlock prevention
4. Atomic primitives — SET NX EX in a single round-trip

---

## SETNX — Legacy Pattern

```
SETNX lock:order:12345 "worker-7"
EXPIRE lock:order:12345 30
```

### Why This Is Dangerous

These are TWO separate commands. If the process crashes between SETNX and EXPIRE:
- The lock is held forever (no TTL)
- No other process can acquire it
- Manual intervention required to delete the key

```python
# DANGEROUS — DO NOT USE IN PRODUCTION
def acquire_lock_legacy(redis_client, lock_key, owner, ttl=30):
    if redis_client.setnx(lock_key, owner):
        # CRASH HERE = PERMANENT DEADLOCK
        redis_client.expire(lock_key, ttl)
        return True
    return False
```

### Historical Context

SETNX was the only option before Redis 2.6.12 (2013). The `SET` command gained `NX` and `EX` flags in that release, making SETNX obsolete for locking. Any codebase still using SETNX + EXPIRE is carrying technical debt.

---

## SET NX EX — Modern Atomic Lock

```
SET lock:order:12345 "worker-7-uuid-abc123" NX EX 30
```

Single atomic command that:
- Sets the key ONLY if it does Not eXist (NX)
- Sets a TTL of 30 seconds (EX 30)
- Returns OK on success, nil on failure

### Production Implementation

```python
import uuid
import time
from contextlib import contextmanager

class RedisLock:
    def __init__(self, redis_client, lock_key, ttl=30):
        self.client = redis_client
        self.lock_key = lock_key
        self.ttl = ttl
        self.owner = str(uuid.uuid4())  # Unique per acquisition
        self._acquired = False

    def acquire(self, timeout=10, retry_interval=0.1):
        """Attempt lock acquisition with retry and timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.client.set(
                self.lock_key,
                self.owner,
                nx=True,
                ex=self.ttl
            )
            if result:
                self._acquired = True
                return True
            time.sleep(retry_interval)
        return False

    def release(self):
        """Release lock ONLY if we still own it."""
        if not self._acquired:
            return False
        # Lua script for atomic check-and-delete
        lua_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        result = self.client.execute_command(
            "EVAL", lua_script, 1, self.lock_key, self.owner
        )
        self._acquired = False
        return result == 1

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Failed to acquire lock: {self.lock_key}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


# Usage
@contextmanager
def distributed_lock(redis_client, resource_id, ttl=30):
    lock = RedisLock(redis_client, f"lock:{resource_id}", ttl)
    try:
        with lock:
            yield lock
    except TimeoutError:
        raise


# Example: preventing double-charge
with distributed_lock(redis, f"payment:{order_id}"):
    process_payment(order_id)
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| UUID as owner value | Prevents accidental release by another process |
| `time.monotonic()` not `time.time()` | Immune to system clock adjustments |
| Retry with sleep | Avoids busy-waiting; configurable backoff |
| Lua for release | Atomic check-and-delete prevents releasing someone else's lock |

---

## Lock Release with Lua Scripts

### The Problem Without Lua

```python
# DANGEROUS — Race condition
def unsafe_release(client, key, owner):
    if client.get(key) == owner:    # Step 1: Check
        # ANOTHER PROCESS ACQUIRES LOCK HERE (our TTL expired)
        client.delete(key)           # Step 2: Delete — WRONG LOCK DELETED
```

Between the GET and DELETE, our TTL might expire, another process acquires the lock, and our DELETE removes THEIR lock.

### The Lua Solution

```lua
-- Atomic: runs as a single operation on Redis server
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

Redis executes Lua scripts atomically — no other command can interleave. The check and delete happen as one unit.

### Using Redis EVAL Command

```python
# Python — using execute_command to call EVAL
RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

# Register script for repeated use (avoids re-parsing)
release_sha = redis_client.script_load(RELEASE_SCRIPT)

# Execute with EVALSHA (cached script)
result = redis_client.execute_command(
    "EVALSHA", release_sha, 1, lock_key, owner_value
)
```

### Extended Lua: Release with Pub/Sub Notification

```lua
-- Release lock AND notify waiting processes
if redis.call("GET", KEYS[1]) == ARGV[1] then
    redis.call("DEL", KEYS[1])
    redis.call("PUBLISH", KEYS[1] .. ":released", ARGV[1])
    return 1
else
    return 0
end
```

---

## Watchdog / TTL Renewal

### The Problem

If a lock has a 30-second TTL but the protected operation takes 45 seconds:
1. Lock expires at t=30
2. Another process acquires the lock at t=31
3. Both processes now operate on the shared resource simultaneously
4. Data corruption

### Watchdog Pattern

A background thread renews the TTL at regular intervals while the lock holder is still active:

```python
import threading

class WatchdogLock(RedisLock):
    def __init__(self, redis_client, lock_key, ttl=30):
        super().__init__(redis_client, lock_key, ttl)
        self._watchdog_thread = None
        self._stop_event = threading.Event()

    def _watchdog_loop(self):
        """Renew TTL at TTL/3 intervals."""
        renewal_interval = self.ttl / 3
        while not self._stop_event.wait(renewal_interval):
            # Atomic: only renew if we still own it
            lua_renew = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("PEXPIRE", KEYS[1], ARGV[2])
            else
                return 0
            end
            """
            result = self.client.execute_command(
                "EVAL", lua_renew, 1,
                self.lock_key, self.owner, str(self.ttl * 1000)
            )
            if result == 0:
                break  # Lost the lock, stop renewing

    def acquire(self, timeout=10, retry_interval=0.1):
        acquired = super().acquire(timeout, retry_interval)
        if acquired:
            self._stop_event.clear()
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True
            )
            self._watchdog_thread.start()
        return acquired

    def release(self):
        self._stop_event.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2)
        return super().release()
```

### Renewal Timing

| TTL | Renewal Interval (TTL/3) | Safety Margin |
|-----|--------------------------|---------------|
| 30s | 10s | 20s before expiry |
| 60s | 20s | 40s before expiry |
| 10s | 3.3s | 6.7s before expiry |

**Why TTL/3?** Gives 2 renewal attempts before expiry. If one renewal fails (network blip), there's still time for a retry.

---

## Redlock Algorithm

### Motivation

A single Redis instance is a single point of failure. If the master crashes after granting a lock but before replicating to the replica:
1. Replica gets promoted to master
2. It has no knowledge of the lock
3. Another process acquires the "same" lock
4. Split-brain: two processes hold the lock

### Algorithm (Martin Kleppmann's refinement)

**Setup:** N independent Redis masters (typically 5). No replication between them.

```
Quorum = floor(N/2) + 1 = 3 (for N=5)
Clock drift factor = 0.01 (1% of TTL)
```

**Acquisition:**

```python
import time
import uuid

class Redlock:
    def __init__(self, redis_instances, ttl=30000):  # ttl in ms
        self.instances = redis_instances  # List of N Redis clients
        self.ttl = ttl
        self.quorum = len(redis_instances) // 2 + 1
        self.clock_drift_factor = 0.01
        self.retry_delay = 200  # ms

    def acquire(self, resource):
        owner = str(uuid.uuid4())
        retry_count = 3

        for attempt in range(retry_count):
            acquired_count = 0
            start_time = time.monotonic() * 1000  # ms

            # Step 1: Try to acquire on all N instances
            for instance in self.instances:
                try:
                    result = instance.set(
                        resource, owner, nx=True, px=self.ttl
                    )
                    if result:
                        acquired_count += 1
                except Exception:
                    pass  # Instance unreachable, skip

            # Step 2: Calculate elapsed time
            elapsed = (time.monotonic() * 1000) - start_time
            drift = self.ttl * self.clock_drift_factor + 2  # ms

            # Step 3: Check if lock is valid
            validity_time = self.ttl - elapsed - drift
            if acquired_count >= self.quorum and validity_time > 0:
                return {
                    "owner": owner,
                    "validity": validity_time,
                    "resource": resource
                }

            # Step 4: Failed — release all instances
            for instance in self.instances:
                self._release_instance(instance, resource, owner)

            # Random delay before retry (avoid thundering herd)
            time.sleep(
                (self.retry_delay + random.randint(0, self.retry_delay)) / 1000
            )

        return None  # Failed to acquire after all retries

    def release(self, lock_info):
        for instance in self.instances:
            self._release_instance(
                instance, lock_info["resource"], lock_info["owner"]
            )

    def _release_instance(self, instance, resource, owner):
        lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        try:
            instance.execute_command("EVAL", lua, 1, resource, owner)
        except Exception:
            pass
```

### The Kleppmann-Antirez Debate

**Martin Kleppmann's critique (2016):**
1. Redlock assumes bounded clock drift — but clocks can jump (NTP, VM migration)
2. Process pauses (GC, page faults) can outlast the lock's validity time
3. No fencing mechanism — stale lock holders can still write
4. "If you need locks for correctness, don't use Redlock. Use a consensus system like ZooKeeper."

**Antirez's response:**
1. Clock jumps can be mitigated with proper NTP configuration
2. The watchdog pattern handles long pauses
3. Fencing tokens can be added on top of Redlock
4. For most applications, Redlock provides sufficient guarantees

**Practical guidance:**
- Use Redlock for **efficiency** (preventing duplicate work) — acceptable
- Use ZooKeeper/etcd for **correctness** (safety-critical mutual exclusion) — required
- If you use Redlock for correctness, ALWAYS add fencing tokens

---

## Fencing Tokens

### The Problem They Solve

```
Timeline:
t=0   Process A acquires lock (validity: 30s)
t=25  Process A enters long GC pause
t=30  Lock expires (TTL)
t=31  Process B acquires lock
t=32  Process B writes to database: balance = 100
t=35  Process A resumes from GC, still thinks it holds the lock
t=36  Process A writes to database: balance = 200 (STALE WRITE)
```

### Solution: Monotonically Increasing Tokens

```python
class FencedLock:
    FENCING_KEY = "global:fencing:counter"

    def acquire(self, resource):
        # Standard lock acquisition
        lock_acquired = self.client.set(
            f"lock:{resource}", self.owner, nx=True, ex=self.ttl
        )
        if not lock_acquired:
            return None

        # Generate fencing token (atomic increment)
        token = self.client.incr(self.FENCING_KEY)
        return {"owner": self.owner, "token": token, "resource": resource}
```

### Using Fencing Tokens in Storage Operations

```python
class FencedStorage:
    """Storage layer that rejects stale writes using fencing tokens."""

    def write(self, key, value, fencing_token):
        # Check: only accept writes with higher tokens
        current_token = self.get_last_token(key)
        if fencing_token <= current_token:
            raise StaleWriteError(
                f"Token {fencing_token} <= current {current_token}"
            )
        # Proceed with write
        self.store(key, value, fencing_token)
```

### Database-Level Fencing (PostgreSQL Example)

```sql
-- Table with fencing token column
CREATE TABLE account_balance (
    account_id UUID PRIMARY KEY,
    balance DECIMAL(15,2) NOT NULL,
    lock_token BIGINT NOT NULL DEFAULT 0
);

-- Update ONLY if our token is newer
UPDATE account_balance
SET balance = $1, lock_token = $2
WHERE account_id = $3 AND lock_token < $2;
-- Rows affected = 0 means stale write was rejected
```

---

## Lease-Based Leader Election

### Pattern

Only one process (the "leader") performs a specific job. Others are standbys. If the leader dies, a standby takes over.

```python
class LeaderElection:
    def __init__(self, redis_client, election_key, node_id, lease_ttl=15):
        self.client = redis_client
        self.election_key = election_key
        self.node_id = node_id
        self.lease_ttl = lease_ttl
        self._is_leader = False
        self._stop_event = threading.Event()

    def campaign(self):
        """Try to become leader. Returns True if elected."""
        result = self.client.set(
            self.election_key, self.node_id, nx=True, ex=self.lease_ttl
        )
        if result:
            self._is_leader = True
            self._start_renewal()
            return True
        # Check if we're already the leader (re-election after restart)
        current_leader = self.client.get(self.election_key)
        if current_leader and current_leader.decode() == self.node_id:
            self._is_leader = True
            self._start_renewal()
            return True
        return False

    def _start_renewal(self):
        """Renew lease in background."""
        def renew_loop():
            while not self._stop_event.wait(self.lease_ttl / 3):
                lua = """
                if redis.call("GET", KEYS[1]) == ARGV[1] then
                    return redis.call("EXPIRE", KEYS[1], ARGV[2])
                else
                    return 0
                end
                """
                result = self.client.execute_command(
                    "EVAL", lua, 1,
                    self.election_key, self.node_id, str(self.lease_ttl)
                )
                if result == 0:
                    self._is_leader = False
                    break

        thread = threading.Thread(target=renew_loop, daemon=True)
        thread.start()

    def resign(self):
        """Voluntarily give up leadership."""
        self._stop_event.set()
        lua = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        self.client.execute_command(
            "EVAL", lua, 1, self.election_key, self.node_id
        )
        self._is_leader = False

    @property
    def is_leader(self):
        return self._is_leader
```

### Epoch-Based Leadership

```python
class EpochLeader:
    """Leader election with epoch numbers to detect stale leaders."""

    def campaign(self):
        # Increment epoch atomically
        epoch = self.client.incr(f"{self.election_key}:epoch")
        # Try to become leader for this epoch
        result = self.client.set(
            self.election_key,
            f"{self.node_id}:{epoch}",
            nx=True,
            ex=self.lease_ttl
        )
        if result:
            self.current_epoch = epoch
            return True
        return False

    def execute_as_leader(self, operation):
        """Only execute if our epoch is still current."""
        stored = self.client.get(self.election_key)
        if stored and stored.decode() == f"{self.node_id}:{self.current_epoch}":
            return operation()
        raise NotLeaderError("Leadership lost or epoch changed")
```

---

## Production Pitfalls

### 1. Clock Skew in Redlock

**Problem:** If one Redis instance's clock runs fast, locks expire early on that instance, breaking quorum.

**Mitigation:**
- Use NTP with `tinkertime panic 0` to prevent large jumps
- Monitor clock drift between instances: alert if > 100ms
- Set TTL accounting for worst-case drift: `effective_ttl = ttl * (1 - clock_drift_factor)`

### 2. Async Replication Failover

**Problem:**
```
t=0  Client acquires lock on master
t=1  Master crashes (lock not yet replicated)
t=2  Replica promoted to master (no lock data)
t=3  Another client acquires the "same" lock
```

**Mitigation:**
- Use `WAIT` command: `WAIT 1 500` (wait for 1 replica ACK within 500ms)
- Accept performance tradeoff (~500ms latency per lock)
- Or use Redlock (independent instances, no replication)

### 3. GC Pauses

**Problem:** A long GC pause (Java, Go) can outlast the lock TTL. Process resumes thinking it still holds the lock.

**Mitigation:**
- Check lock ownership before every critical write (re-verify with GET)
- Use fencing tokens — storage layer rejects stale writes regardless
- Tune GC: reduce max pause time, use ZGC/Shenandoah for Java

### 4. Thundering Herd on Lock Release

**Problem:** 100 processes waiting for a lock. Lock released. All 100 race to acquire simultaneously.

**Mitigation:**
```python
# Randomized retry delay with exponential backoff
def acquire_with_backoff(self, max_attempts=10):
    for attempt in range(max_attempts):
        if self._try_acquire():
            return True
        # Exponential backoff with jitter
        delay = min(
            (2 ** attempt) * 0.05 + random.uniform(0, 0.05),
            2.0  # Cap at 2 seconds
        )
        time.sleep(delay)
    return False
```

### 5. Lock Key Naming Collisions

**Problem:** Two different services use `lock:user:123` for different purposes.

**Mitigation:**
```python
# Always include service name and purpose in key
LOCK_KEY_PATTERN = "lock:{service}:{resource_type}:{resource_id}"
# Example: "lock:payment-svc:order:12345"
# Example: "lock:inventory-svc:sku:ABC-789"
```

### 6. Deadlocks in Multi-Resource Locking

**Problem:** Process A holds lock on resource X, waiting for Y. Process B holds Y, waiting for X.

**Mitigation:**
```python
def acquire_multiple_locks(redis_client, resources, ttl=30):
    """Acquire locks in deterministic order to prevent deadlocks."""
    # ALWAYS sort resources — consistent ordering prevents circular waits
    sorted_resources = sorted(resources)
    acquired = []

    try:
        for resource in sorted_resources:
            lock = RedisLock(redis_client, f"lock:{resource}", ttl)
            if not lock.acquire(timeout=5):
                raise LockAcquisitionError(f"Failed: {resource}")
            acquired.append(lock)
        return acquired
    except LockAcquisitionError:
        # Rollback: release all acquired locks
        for lock in reversed(acquired):
            lock.release()
        raise
```

---

## Multi-Language Implementations

### Java — Redisson

```java
// Redisson provides automatic watchdog renewal (30s default, renews at 10s)
RLock lock = redissonClient.getLock("lock:order:12345");

try {
    // Wait up to 10s to acquire, lease for 30s (with auto-renewal)
    boolean acquired = lock.tryLock(10, 30, TimeUnit.SECONDS);
    if (acquired) {
        processOrder();
    }
} finally {
    if (lock.isHeldByCurrentThread()) {
        lock.unlock();
    }
}

// Redlock with Redisson (multiple instances)
RLock lock1 = redisson1.getLock("lock:order:12345");
RLock lock2 = redisson2.getLock("lock:order:12345");
RLock lock3 = redisson3.getLock("lock:order:12345");
RedissonRedLock redLock = new RedissonRedLock(lock1, lock2, lock3);
redLock.lock();
try {
    processOrder();
} finally {
    redLock.unlock();
}
```

### Go — redsync

```go
package main

import (
    "github.com/go-redsync/redsync/v4"
    "github.com/go-redsync/redsync/v4/redis/goredis/v9"
    goredislib "github.com/redis/go-redis/v9"
)

func main() {
    client := goredislib.NewClient(&goredislib.Options{Addr: "localhost:6379"})
    pool := goredis.NewPool(client)
    rs := redsync.New(pool)

    mutex := rs.NewMutex("lock:order:12345",
        redsync.WithExpiry(30*time.Second),
        redsync.WithTries(10),
        redsync.WithRetryDelay(100*time.Millisecond),
    )

    if err := mutex.Lock(); err != nil {
        log.Fatal(err)
    }
    defer mutex.Unlock()

    processOrder()
}
```

### Node.js — ioredis + custom

```javascript
const Redis = require('ioredis');
const { v4: uuidv4 } = require('uuid');

class RedisLock {
  constructor(client, key, ttl = 30) {
    this.client = client;
    this.key = key;
    this.ttl = ttl;
    this.owner = uuidv4();
  }

  async acquire(timeout = 10000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      const result = await this.client.set(
        this.key, this.owner, 'NX', 'EX', this.ttl
      );
      if (result === 'OK') return true;
      await new Promise(r => setTimeout(r, 100));
    }
    return false;
  }

  async release() {
    const lua = `
      if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
      else
        return 0
      end
    `;
    return await this.client.call('EVAL', lua, 1, this.key, this.owner);
  }
}

// Usage
const lock = new RedisLock(redis, 'lock:order:12345');
if (await lock.acquire()) {
  try {
    await processOrder();
  } finally {
    await lock.release();
  }
}
```

---

## Observability & Monitoring

### Key Metrics to Track

| Metric | Type | Alert Threshold |
|--------|------|-----------------|
| `lock_acquisition_duration_ms` | Histogram | p99 > 5000ms |
| `lock_acquisition_failures_total` | Counter | > 10/min per resource |
| `lock_held_duration_ms` | Histogram | p99 > TTL * 0.8 |
| `lock_renewal_failures_total` | Counter | Any (indicates lost lock) |
| `lock_ownership_violations` | Counter | Any (critical — split brain) |
| `lock_ttl_expirations` | Counter | > 0 (operation took too long) |

### Prometheus Instrumentation

```python
from prometheus_client import Histogram, Counter

LOCK_ACQUIRE_DURATION = Histogram(
    'redis_lock_acquire_duration_seconds',
    'Time to acquire a distributed lock',
    ['resource_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)

LOCK_FAILURES = Counter(
    'redis_lock_acquire_failures_total',
    'Failed lock acquisition attempts',
    ['resource_type', 'reason']
)

LOCK_HELD_DURATION = Histogram(
    'redis_lock_held_duration_seconds',
    'Duration lock was held before release',
    ['resource_type'],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
)
```

### Alerting Rules

```yaml
# Prometheus alerting rules
groups:
  - name: redis_locks
    rules:
      - alert: LockAcquisitionSlow
        expr: histogram_quantile(0.99, redis_lock_acquire_duration_seconds) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Lock acquisition p99 exceeds 5 seconds"

      - alert: LockOwnershipViolation
        expr: increase(redis_lock_ownership_violations[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Split-brain detected: multiple lock owners"

      - alert: LockTTLExpirations
        expr: increase(redis_lock_ttl_expirations[5m]) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Locks expiring before release — operations taking too long"
```

---

## Decision Matrix: Which Lock to Use

| Scenario | Recommendation | Reason |
|----------|---------------|--------|
| Single Redis, efficiency lock | SET NX EX + Lua release | Simple, fast, good enough |
| Single Redis, correctness needed | SET NX EX + fencing tokens | Prevents stale writes |
| Multi-region, high availability | Redlock (5 instances) | Tolerates N/2 failures |
| Safety-critical (financial) | ZooKeeper / etcd | Consensus protocol, linearizable |
| Short-lived locks (< 1s) | SET NX PX + no watchdog | Overhead of watchdog > benefit |
| Long-lived locks (minutes) | SET NX EX + watchdog | Prevents premature expiry |
| Leader election | Lease pattern with epochs | Clean failover semantics |

---

## Summary of Commands

```redis
-- Acquire lock (atomic)
SET lock:resource:id "owner-uuid" NX EX 30

-- Check lock owner
GET lock:resource:id

-- Extend lock (only if owner matches — use Lua)
EVAL "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('EXPIRE',KEYS[1],ARGV[2]) else return 0 end" 1 lock:resource:id owner-uuid 30

-- Release lock (only if owner matches — use Lua)
EVAL "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end" 1 lock:resource:id owner-uuid

-- Fencing token generation
INCR global:fencing:counter

-- Wait for replication (before confirming lock)
WAIT 1 500
```
