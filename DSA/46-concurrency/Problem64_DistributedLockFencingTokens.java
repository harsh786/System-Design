import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.*;

/**
 * Problem 64: Distributed Lock with Fencing Tokens
 * 
 * REAL-WORLD USAGE:
 * - ZooKeeper ephemeral nodes + sequential znodes
 * - Redis Redlock (though controversial without fencing)
 * - etcd lease-based locks with revision numbers
 * - Database advisory locks with sequence numbers
 * - Chubby (Google's lock service)
 * 
 * THE PROBLEM WITH NAIVE DISTRIBUTED LOCKS:
 * 1. Client A acquires lock, starts work
 * 2. Client A has a long GC pause (or network partition)
 * 3. Lock expires (TTL), Client B acquires the lock
 * 4. Client A resumes, THINKS it still has the lock
 * 5. Both A and B write to shared resource → DATA CORRUPTION
 * 
 * SOLUTION: FENCING TOKENS
 * - Lock service issues a monotonically increasing token with each lock grant
 * - Client includes the token in all writes to the resource
 * - Resource server rejects writes with tokens LOWER than the highest seen
 * - Client A's stale token (e.g., 42) is rejected because B has token 43
 * 
 * MEMORY ORDERING:
 * - Fencing token must be generated atomically with lock grant
 * - Resource server's highest-seen-token check must be atomic with the write
 * - Token comparison is the linearization point for mutual exclusion
 * 
 * PITFALLS:
 * 1. Redis Redlock WITHOUT fencing tokens is NOT safe (Martin Kleppmann's analysis)
 * 2. Tokens must be monotonically increasing (not just unique)
 * 3. Resource server MUST enforce fencing (client-side only is insufficient)
 * 4. Clock skew can cause premature lock expiry (use monotonic clocks for TTL)
 */
public class Problem64_DistributedLockFencingTokens {

    // ==================== LOCK SERVICE ====================
    static class DistributedLockService {
        private final AtomicLong fencingTokenCounter = new AtomicLong(0);
        private final ConcurrentHashMap<String, LockEntry> locks = new ConcurrentHashMap<>();

        static class LockEntry {
            volatile String owner;
            volatile long fencingToken;
            volatile long expiresAt; // Simulated TTL

            LockEntry(String owner, long token, long expiresAt) {
                this.owner = owner;
                this.fencingToken = token;
                this.expiresAt = expiresAt;
            }
        }

        /**
         * Acquire lock. Returns fencing token on success, -1 on failure.
         * The fencing token is MONOTONICALLY INCREASING - this is critical.
         */
        public synchronized long acquire(String lockName, String clientId, long ttlMs) {
            LockEntry entry = locks.get(lockName);
            long now = System.currentTimeMillis();

            if (entry != null && entry.expiresAt > now && !entry.owner.equals(clientId)) {
                return -1; // Lock held by another client and not expired
            }

            // Grant lock with new fencing token
            long token = fencingTokenCounter.incrementAndGet();
            locks.put(lockName, new LockEntry(clientId, token, now + ttlMs));
            return token;
        }

        public synchronized boolean release(String lockName, String clientId, long token) {
            LockEntry entry = locks.get(lockName);
            if (entry != null && entry.owner.equals(clientId) && entry.fencingToken == token) {
                locks.remove(lockName);
                return true;
            }
            return false;
        }

        /** Simulate TTL expiry check */
        public synchronized void expireStale() {
            long now = System.currentTimeMillis();
            locks.entrySet().removeIf(e -> e.getValue().expiresAt < now);
        }
    }

    // ==================== RESOURCE SERVER (with fencing) ====================
    static class FencedResourceServer {
        private final ConcurrentHashMap<String, String> data = new ConcurrentHashMap<>();
        private final ConcurrentHashMap<String, Long> highestToken = new ConcurrentHashMap<>();
        private final AtomicInteger rejectedWrites = new AtomicInteger(0);
        private final AtomicInteger acceptedWrites = new AtomicInteger(0);

        /**
         * Write with fencing token. Rejects if token < highest seen.
         * This is the KEY defense against stale lock holders.
         */
        public boolean write(String key, String value, long fencingToken) {
            synchronized (this) { // Atomic check-and-update of highest token
                Long highest = highestToken.get(key);
                if (highest != null && fencingToken < highest) {
                    // REJECT: this client has a stale lock
                    rejectedWrites.incrementAndGet();
                    return false;
                }
                highestToken.put(key, fencingToken);
                data.put(key, value);
                acceptedWrites.incrementAndGet();
                return true;
            }
        }

        public String read(String key) { return data.get(key); }
        public int getRejectedWrites() { return rejectedWrites.get(); }
        public int getAcceptedWrites() { return acceptedWrites.get(); }
    }

    // ==================== CLIENT ====================
    static class DistributedClient implements Runnable {
        private final String clientId;
        private final DistributedLockService lockService;
        private final FencedResourceServer resource;
        private final int numOperations;
        private final AtomicInteger successOps = new AtomicInteger(0);
        private final AtomicInteger failedAcquires = new AtomicInteger(0);

        DistributedClient(String clientId, DistributedLockService lockService,
                         FencedResourceServer resource, int numOperations) {
            this.clientId = clientId;
            this.lockService = lockService;
            this.resource = resource;
            this.numOperations = numOperations;
        }

        @Override
        public void run() {
            Random rng = new Random();
            for (int i = 0; i < numOperations; i++) {
                String lockName = "resource-" + (i % 5);
                long token = lockService.acquire(lockName, clientId, 50); // 50ms TTL

                if (token < 0) {
                    failedAcquires.incrementAndGet();
                    continue;
                }

                // Simulate work (may exceed TTL, causing stale lock)
                if (rng.nextInt(100) < 5) { // 5% chance of "GC pause"
                    try { Thread.sleep(60); } catch (InterruptedException e) { return; }
                }

                // Write WITH fencing token
                boolean written = resource.write(lockName, clientId + "-" + i, token);
                if (written) successOps.incrementAndGet();

                lockService.release(lockName, clientId, token);
            }
        }

        public int getSuccessOps() { return successOps.get(); }
        public int getFailedAcquires() { return failedAcquires.get(); }
    }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Distributed Lock with Fencing Tokens ===\n");

        // Demo: fencing token prevents stale writes
        System.out.println("--- Fencing Token Demo ---");
        DistributedLockService lockService = new DistributedLockService();
        FencedResourceServer resource = new FencedResourceServer();

        long tokenA = lockService.acquire("mylock", "clientA", 100);
        System.out.println("Client A acquires lock, token=" + tokenA);

        // Simulate A's lock expiring
        Thread.sleep(110);
        lockService.expireStale();

        long tokenB = lockService.acquire("mylock", "clientB", 100);
        System.out.println("Client B acquires lock (after A expired), token=" + tokenB);

        // B writes successfully
        boolean bWrite = resource.write("shared-key", "B-value", tokenB);
        System.out.println("Client B writes: " + (bWrite ? "ACCEPTED" : "REJECTED"));

        // A tries to write with STALE token
        boolean aWrite = resource.write("shared-key", "A-stale-value", tokenA);
        System.out.println("Client A writes (stale token): " + (aWrite ? "ACCEPTED" : "REJECTED (fenced!)"));
        System.out.println("Resource value: " + resource.read("shared-key") + " (correctly B's value)\n");

        // Stress test
        System.out.println("--- Concurrent Clients Stress Test ---");
        DistributedLockService stressLockService = new DistributedLockService();
        FencedResourceServer stressResource = new FencedResourceServer();
        int numClients = 8;
        int opsPerClient = 5_000;
        List<DistributedClient> clients = new ArrayList<>();
        List<Thread> threads = new ArrayList<>();

        // Background expiry thread
        Thread expiryThread = new Thread(() -> {
            while (!Thread.interrupted()) {
                stressLockService.expireStale();
                try { Thread.sleep(10); } catch (InterruptedException e) { return; }
            }
        });
        expiryThread.setDaemon(true);
        expiryThread.start();

        long start = System.nanoTime();
        for (int i = 0; i < numClients; i++) {
            DistributedClient client = new DistributedClient(
                    "client-" + i, stressLockService, stressResource, opsPerClient);
            clients.add(client);
            Thread t = new Thread(client);
            threads.add(t);
            t.start();
        }

        for (Thread t : threads) t.join();
        long elapsed = System.nanoTime() - start;
        expiryThread.interrupt();

        int totalOps = numClients * opsPerClient;
        int successOps = clients.stream().mapToInt(DistributedClient::getSuccessOps).sum();
        int failedAcquires = clients.stream().mapToInt(DistributedClient::getFailedAcquires).sum();

        System.out.println("Clients: " + numClients + ", Ops/client: " + opsPerClient);
        System.out.println("Successful writes: " + successOps);
        System.out.println("Failed lock acquires: " + failedAcquires);
        System.out.println("Fenced (rejected) writes: " + stressResource.getRejectedWrites());
        System.out.println("Accepted writes: " + stressResource.getAcceptedWrites());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("\nKey insight: Fencing tokens are the ONLY way to make distributed locks safe.");
        System.out.println("Without fencing, GC pauses or network delays cause split-brain writes.");
    }
}
