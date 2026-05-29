import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 55: Distributed Lock with Fencing Tokens
 * 
 * PRODUCTION MAPPING: Redis Redlock, ZooKeeper locks, etcd lease-based locks, Chubby
 * 
 * Key Concepts:
 * - Fencing tokens: monotonically increasing token to prevent stale lock holders
 *   from corrupting shared resources (Martin Kleppmann's critique of Redlock)
 * - TTL: lock auto-expires to prevent deadlocks from crashed holders
 * - Reentrancy: same owner can re-acquire (increment count)
 * 
 * Why fencing tokens matter (staff-level insight):
 * - Process A acquires lock (token=33), then GC pause
 * - Lock expires, Process B acquires lock (token=34)
 * - Process A wakes up, thinks it still has lock
 * - Without fencing: A corrupts data. With fencing: resource rejects token=33 < 34
 * 
 * Trade-offs:
 * - TTL too short: lock expires during legitimate operation
 * - TTL too long: resources blocked if holder crashes
 * - Solution: lock renewal (watchdog thread, like Redisson's)
 */
public class Problem55_DistributedLock {

    static class LockManager {
        private final Map<String, LockEntry> locks = new ConcurrentHashMap<>();
        private final AtomicLong fencingTokenGenerator = new AtomicLong(0);
        private final ScheduledExecutorService expiryChecker;

        static class LockEntry {
            final String owner;
            final long fencingToken;
            final long expiryTime;
            final int reentrantCount;

            LockEntry(String owner, long fencingToken, long expiryTime, int reentrantCount) {
                this.owner = owner;
                this.fencingToken = fencingToken;
                this.expiryTime = expiryTime;
                this.reentrantCount = reentrantCount;
            }
        }

        public LockManager() {
            expiryChecker = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "lock-expiry");
                t.setDaemon(true);
                return t;
            });
            expiryChecker.scheduleAtFixedRate(this::cleanExpired, 100, 100, TimeUnit.MILLISECONDS);
        }

        /**
         * Try to acquire lock. Returns fencing token on success, -1 on failure.
         */
        public synchronized long tryLock(String resource, String owner, long ttlMs) {
            LockEntry existing = locks.get(resource);
            long now = System.currentTimeMillis();

            // Check if lock is free or expired
            if (existing == null || now > existing.expiryTime) {
                long token = fencingTokenGenerator.incrementAndGet();
                locks.put(resource, new LockEntry(owner, token, now + ttlMs, 1));
                return token;
            }

            // Reentrant: same owner can re-acquire
            if (existing.owner.equals(owner)) {
                long token = existing.fencingToken; // same token for reentrant
                locks.put(resource, new LockEntry(owner, token, now + ttlMs, 
                    existing.reentrantCount + 1));
                return token;
            }

            return -1; // Lock held by another owner
        }

        /**
         * Blocking acquire with timeout
         */
        public long lock(String resource, String owner, long ttlMs, long waitTimeoutMs) 
                throws InterruptedException {
            long deadline = System.currentTimeMillis() + waitTimeoutMs;
            while (System.currentTimeMillis() < deadline) {
                long token = tryLock(resource, owner, ttlMs);
                if (token != -1) return token;
                Thread.sleep(10); // backoff
            }
            return -1; // timeout
        }

        /**
         * Release lock. Only owner can release.
         */
        public synchronized boolean unlock(String resource, String owner) {
            LockEntry entry = locks.get(resource);
            if (entry == null) return false;
            if (!entry.owner.equals(owner)) return false;

            if (entry.reentrantCount > 1) {
                locks.put(resource, new LockEntry(owner, entry.fencingToken,
                    entry.expiryTime, entry.reentrantCount - 1));
            } else {
                locks.remove(resource);
            }
            return true;
        }

        /**
         * Extend lock TTL (watchdog pattern like Redisson)
         */
        public synchronized boolean renewLock(String resource, String owner, long newTtlMs) {
            LockEntry entry = locks.get(resource);
            if (entry == null || !entry.owner.equals(owner)) return false;
            locks.put(resource, new LockEntry(owner, entry.fencingToken,
                System.currentTimeMillis() + newTtlMs, entry.reentrantCount));
            return true;
        }

        public synchronized boolean isLocked(String resource) {
            LockEntry entry = locks.get(resource);
            return entry != null && System.currentTimeMillis() <= entry.expiryTime;
        }

        private synchronized void cleanExpired() {
            long now = System.currentTimeMillis();
            locks.entrySet().removeIf(e -> now > e.getValue().expiryTime);
        }

        public void shutdown() { expiryChecker.shutdown(); }
    }

    /**
     * Simulates a shared resource that validates fencing tokens
     */
    static class FencedResource {
        private long highestSeenToken = 0;
        private String lastWriter = "none";

        public synchronized boolean write(String data, long fencingToken) {
            if (fencingToken < highestSeenToken) {
                // Reject stale write - this is the key safety property!
                return false;
            }
            highestSeenToken = fencingToken;
            lastWriter = data;
            return true;
        }

        public String getLastWriter() { return lastWriter; }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Distributed Lock with Fencing Tokens ===\n");
        LockManager lm = new LockManager();

        // Test 1: Basic acquire/release
        long token = lm.tryLock("resource-1", "owner-A", 5000);
        assert token > 0 : "Should acquire lock";
        assert lm.isLocked("resource-1");
        lm.unlock("resource-1", "owner-A");
        assert !lm.isLocked("resource-1");
        System.out.println("PASS: Basic acquire/release");

        // Test 2: Mutual exclusion
        lm.tryLock("resource-1", "owner-A", 5000);
        long denied = lm.tryLock("resource-1", "owner-B", 5000);
        assert denied == -1 : "B should be denied";
        lm.unlock("resource-1", "owner-A");
        System.out.println("PASS: Mutual exclusion");

        // Test 3: Fencing tokens are monotonically increasing
        long t1 = lm.tryLock("r", "A", 5000);
        lm.unlock("r", "A");
        long t2 = lm.tryLock("r", "B", 5000);
        lm.unlock("r", "B");
        assert t2 > t1 : "Tokens must be monotonically increasing";
        System.out.println("PASS: Fencing tokens increase: " + t1 + " < " + t2);

        // Test 4: Fencing token prevents stale writes
        FencedResource resource = new FencedResource();
        long tokenA = lm.tryLock("data", "A", 5000);
        lm.unlock("data", "A");
        long tokenB = lm.tryLock("data", "B", 5000);
        
        // B writes first (has higher token)
        assert resource.write("B-wrote", tokenB);
        // A tries to write with stale token - REJECTED
        assert !resource.write("A-stale-write", tokenA);
        assert resource.getLastWriter().equals("B-wrote");
        lm.unlock("data", "B");
        System.out.println("PASS: Fencing token prevents stale writes");

        // Test 5: TTL expiry
        lm.tryLock("ephemeral", "holder", 100);
        Thread.sleep(150);
        assert !lm.isLocked("ephemeral") : "Lock should expire";
        long newToken = lm.tryLock("ephemeral", "new-holder", 5000);
        assert newToken > 0 : "Should acquire expired lock";
        lm.unlock("ephemeral", "new-holder");
        System.out.println("PASS: TTL expiry releases lock");

        // Test 6: Reentrancy
        long rt1 = lm.tryLock("reentrant", "owner", 5000);
        long rt2 = lm.tryLock("reentrant", "owner", 5000); // same owner
        assert rt1 == rt2 : "Reentrant should return same token";
        lm.unlock("reentrant", "owner"); // decrement count
        assert lm.isLocked("reentrant") : "Still locked (count=1)";
        lm.unlock("reentrant", "owner"); // fully released
        assert !lm.isLocked("reentrant");
        System.out.println("PASS: Reentrant locking");

        // Test 7: Only owner can release
        lm.tryLock("owned", "A", 5000);
        boolean released = lm.unlock("owned", "B"); // wrong owner
        assert !released : "Non-owner cannot release";
        assert lm.isLocked("owned");
        lm.unlock("owned", "A");
        System.out.println("PASS: Only owner can release");

        // Test 8: Lock renewal
        lm.tryLock("renewable", "worker", 200);
        Thread.sleep(100);
        lm.renewLock("renewable", "worker", 200); // extend
        Thread.sleep(150); // original would have expired
        assert lm.isLocked("renewable") : "Should still be locked after renewal";
        lm.unlock("renewable", "worker");
        System.out.println("PASS: Lock renewal extends TTL");

        lm.shutdown();
        System.out.println("\nAll tests passed!");
    }
}
