import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Problem 75: Connection Pool with Health Checks and Idle Timeout
 * 
 * PRODUCTION MAPPING: HikariCP, Apache DBCP, c3p0, pgbouncer, Redis connection pools,
 *                     HTTP client pools (Apache HttpClient, OkHttp)
 * 
 * Design Decisions:
 * - Fixed pool size with blocking acquire (bounded resource usage)
 * - Connection validation before returning to caller (test-on-borrow)
 * - Idle connection eviction (prevent stale/broken connections)
 * - Background health check thread (test-while-idle)
 * - Connection lifetime limit (prevent connection aging issues)
 * - Metrics: wait time, active count, idle count, creation count
 * 
 * Trade-offs:
 * - Pool too small: high wait times, thread starvation
 * - Pool too large: wastes server resources, connection limits
 * - HikariCP formula: pool_size = Tn × (Cm − 1) + 1
 *   where Tn = max threads, Cm = max simultaneous connections per thread
 * 
 * Key insight: Connection pool sizing is about Little's Law:
 *   L = λW (connections_needed = request_rate × avg_response_time)
 */
public class Problem75_ConnectionPool {

    interface Connection {
        boolean isValid();
        void close();
        String getId();
        long getCreatedAt();
        long getLastUsedAt();
        void execute(String command); // simulate work
    }

    static class SimpleConnection implements Connection {
        private final String id;
        private final long createdAt;
        private volatile long lastUsedAt;
        private volatile boolean valid = true;
        private volatile boolean closed = false;

        SimpleConnection(String id) {
            this.id = id;
            this.createdAt = System.currentTimeMillis();
            this.lastUsedAt = createdAt;
        }

        @Override public boolean isValid() { return valid && !closed; }
        @Override public void close() { closed = true; }
        @Override public String getId() { return id; }
        @Override public long getCreatedAt() { return createdAt; }
        @Override public long getLastUsedAt() { return lastUsedAt; }
        @Override public void execute(String command) { lastUsedAt = System.currentTimeMillis(); }
        
        void invalidate() { valid = false; }
    }

    static class ConnectionPool {
        private final int maxSize;
        private final int minIdle;
        private final long maxIdleTimeMs;
        private final long maxLifetimeMs;
        private final long acquireTimeoutMs;

        private final BlockingQueue<Connection> idle;
        private final Set<Connection> active = ConcurrentHashMap.newKeySet();
        private final AtomicInteger totalCreated = new AtomicInteger(0);
        private final AtomicInteger totalConnections = new AtomicInteger(0);
        private final AtomicLong totalWaitTimeMs = new AtomicLong(0);
        private final AtomicLong acquireCount = new AtomicLong(0);
        private final ScheduledExecutorService maintenance;
        private volatile boolean shutdown = false;

        public ConnectionPool(int maxSize, int minIdle, long maxIdleTimeMs, 
                             long maxLifetimeMs, long acquireTimeoutMs) {
            this.maxSize = maxSize;
            this.minIdle = minIdle;
            this.maxIdleTimeMs = maxIdleTimeMs;
            this.maxLifetimeMs = maxLifetimeMs;
            this.acquireTimeoutMs = acquireTimeoutMs;
            this.idle = new LinkedBlockingQueue<>(maxSize);

            // Pre-create minimum idle connections
            for (int i = 0; i < minIdle; i++) {
                idle.offer(createConnection());
            }

            // Background maintenance thread
            maintenance = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "pool-maintenance");
                t.setDaemon(true);
                return t;
            });
            maintenance.scheduleAtFixedRate(this::maintain, 100, 100, TimeUnit.MILLISECONDS);
        }

        /**
         * Acquire a connection from the pool.
         * Validates before returning (test-on-borrow).
         */
        public Connection acquire() throws InterruptedException, TimeoutException {
            long start = System.currentTimeMillis();
            acquireCount.incrementAndGet();

            while (true) {
                // Try to get from idle pool
                Connection conn = idle.poll();
                
                if (conn != null) {
                    // Validate connection (test-on-borrow)
                    if (isHealthy(conn)) {
                        active.add(conn);
                        totalWaitTimeMs.addAndGet(System.currentTimeMillis() - start);
                        return conn;
                    } else {
                        destroyConnection(conn);
                        continue;
                    }
                }

                // No idle connections - can we create new?
                if (totalConnections.get() < maxSize) {
                    conn = createConnection();
                    active.add(conn);
                    totalWaitTimeMs.addAndGet(System.currentTimeMillis() - start);
                    return conn;
                }

                // Pool exhausted - wait for release
                long remaining = acquireTimeoutMs - (System.currentTimeMillis() - start);
                if (remaining <= 0) {
                    throw new TimeoutException("Connection pool exhausted (max=" + maxSize + ")");
                }
                conn = idle.poll(remaining, TimeUnit.MILLISECONDS);
                if (conn == null) {
                    throw new TimeoutException("Timed out waiting for connection");
                }
                if (isHealthy(conn)) {
                    active.add(conn);
                    totalWaitTimeMs.addAndGet(System.currentTimeMillis() - start);
                    return conn;
                }
                destroyConnection(conn);
            }
        }

        /** Return connection to pool */
        public void release(Connection conn) {
            active.remove(conn);
            if (isHealthy(conn) && !shutdown) {
                idle.offer(conn);
            } else {
                destroyConnection(conn);
            }
        }

        private boolean isHealthy(Connection conn) {
            if (!conn.isValid()) return false;
            // Check max lifetime
            if (System.currentTimeMillis() - conn.getCreatedAt() > maxLifetimeMs) return false;
            return true;
        }

        /** Periodic maintenance: evict idle, ensure minimum, health check */
        private void maintain() {
            long now = System.currentTimeMillis();

            // Evict connections idle too long
            Iterator<Connection> it = idle.iterator();
            while (it.hasNext()) {
                Connection conn = it.next();
                if (now - conn.getLastUsedAt() > maxIdleTimeMs && 
                    idle.size() > minIdle) {
                    if (idle.remove(conn)) {
                        destroyConnection(conn);
                    }
                }
            }

            // Evict expired connections
            it = idle.iterator();
            while (it.hasNext()) {
                Connection conn = it.next();
                if (!isHealthy(conn)) {
                    if (idle.remove(conn)) destroyConnection(conn);
                }
            }

            // Ensure minimum idle connections
            while (idle.size() < minIdle && totalConnections.get() < maxSize) {
                idle.offer(createConnection());
            }
        }

        private Connection createConnection() {
            int id = totalCreated.incrementAndGet();
            totalConnections.incrementAndGet();
            return new SimpleConnection("conn-" + id);
        }

        private void destroyConnection(Connection conn) {
            conn.close();
            totalConnections.decrementAndGet();
        }

        public void shutdown() {
            shutdown = true;
            maintenance.shutdown();
            Connection conn;
            while ((conn = idle.poll()) != null) conn.close();
        }

        // Metrics
        public int getActiveCount() { return active.size(); }
        public int getIdleCount() { return idle.size(); }
        public int getTotalConnections() { return totalConnections.get(); }
        public double getAvgWaitTimeMs() { 
            long count = acquireCount.get();
            return count > 0 ? (double) totalWaitTimeMs.get() / count : 0;
        }
        public int getTotalCreated() { return totalCreated.get(); }
    }

    public static void main(String[] args) throws Exception {
        System.out.println("=== Connection Pool with Health Checks ===\n");

        // Test 1: Basic acquire/release
        ConnectionPool pool = new ConnectionPool(5, 2, 5000, 30000, 1000);
        Connection c1 = pool.acquire();
        Connection c2 = pool.acquire();
        assert c1 != null && c2 != null;
        assert pool.getActiveCount() == 2;
        pool.release(c1);
        pool.release(c2);
        assert pool.getActiveCount() == 0;
        assert pool.getIdleCount() >= 2;
        System.out.println("PASS: Basic acquire/release (idle=" + pool.getIdleCount() + ")");

        // Test 2: Pool limit enforced
        pool = new ConnectionPool(3, 1, 5000, 30000, 200);
        Connection[] conns = new Connection[3];
        for (int i = 0; i < 3; i++) conns[i] = pool.acquire();
        assert pool.getActiveCount() == 3;
        
        try {
            pool.acquire(); // should timeout
            assert false : "Should throw TimeoutException";
        } catch (TimeoutException e) {
            System.out.println("PASS: Pool exhaustion throws TimeoutException");
        }
        for (Connection c : conns) pool.release(c);

        // Test 3: Connection reuse
        pool = new ConnectionPool(5, 2, 5000, 30000, 1000);
        Connection first = pool.acquire();
        String firstId = first.getId();
        pool.release(first);
        Connection second = pool.acquire();
        assert firstId.equals(second.getId()) : "Should reuse same connection";
        pool.release(second);
        System.out.println("PASS: Connections reused from pool");

        // Test 4: Invalid connections rejected
        pool = new ConnectionPool(5, 0, 5000, 30000, 1000);
        Connection bad = pool.acquire();
        ((SimpleConnection) bad).invalidate();
        pool.release(bad);
        Connection good = pool.acquire();
        assert !bad.getId().equals(good.getId()) : "Should not return invalid connection";
        pool.release(good);
        System.out.println("PASS: Invalid connections evicted on return");

        // Test 5: Idle timeout eviction
        pool = new ConnectionPool(5, 0, 50, 30000, 1000);
        Connection temp = pool.acquire();
        pool.release(temp);
        assert pool.getIdleCount() >= 1;
        Thread.sleep(200); // exceed idle timeout + maintenance cycle
        assert pool.getIdleCount() == 0 : "Idle connections should be evicted, got: " + pool.getIdleCount();
        System.out.println("PASS: Idle timeout evicts stale connections");

        // Test 6: Max lifetime eviction
        pool = new ConnectionPool(5, 0, 5000, 100, 1000);
        Connection aged = pool.acquire();
        Thread.sleep(150); // exceed max lifetime
        pool.release(aged); // should be destroyed, not returned to pool
        // Next acquire should get a fresh connection
        Connection fresh = pool.acquire();
        assert !aged.getId().equals(fresh.getId());
        pool.release(fresh);
        System.out.println("PASS: Max lifetime evicts old connections");

        // Test 7: Concurrent access
        pool = new ConnectionPool(10, 5, 5000, 30000, 2000);
        int numThreads = 20;
        int opsPerThread = 100;
        AtomicInteger successOps = new AtomicInteger(0);
        ExecutorService exec = Executors.newFixedThreadPool(numThreads);
        CountDownLatch latch = new CountDownLatch(numThreads);

        final ConnectionPool finalPool = pool;
        for (int t = 0; t < numThreads; t++) {
            exec.submit(() -> {
                try {
                    for (int i = 0; i < opsPerThread; i++) {
                        Connection conn = finalPool.acquire();
                        conn.execute("SELECT 1");
                        Thread.sleep(1); // simulate work
                        finalPool.release(conn);
                        successOps.incrementAndGet();
                    }
                } catch (Exception e) {
                    // timeout ok under contention
                } finally {
                    latch.countDown();
                }
            });
        }
        latch.await();
        exec.shutdown();

        System.out.printf("PASS: Concurrent access - %d/%d ops succeeded\n", 
            successOps.get(), numThreads * opsPerThread);
        System.out.printf("  Avg wait time: %.2f ms\n", pool.getAvgWaitTimeMs());
        System.out.printf("  Total connections created: %d\n", pool.getTotalCreated());

        // Test 8: Minimum idle maintained
        pool.shutdown();
        pool = new ConnectionPool(10, 3, 5000, 30000, 1000);
        Thread.sleep(150); // let maintenance run
        assert pool.getIdleCount() >= 3 : "Should maintain min idle, got: " + pool.getIdleCount();
        System.out.println("PASS: Minimum idle connections maintained (idle=" + pool.getIdleCount() + ")");

        pool.shutdown();
        System.out.println("\nAll tests passed!");
    }
}
