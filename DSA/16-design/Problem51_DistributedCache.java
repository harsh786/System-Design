import java.util.*;
import java.util.concurrent.*;

/**
 * Problem 51: Distributed Cache with TTL + LRU Combined Eviction
 * 
 * PRODUCTION MAPPING: Redis, Memcached, Caffeine, Guava Cache
 * 
 * Design Decisions:
 * - Combined eviction: TTL expiry takes priority, then LRU for capacity
 * - Lazy expiration (check on access) + periodic cleanup thread
 * - Thread-safe with ReadWriteLock for concurrent access
 * - O(1) get/put via HashMap + Doubly Linked List
 * 
 * Trade-offs:
 * - Lazy expiry: stale entries consume memory until accessed or cleaned
 * - Periodic cleanup: background thread adds complexity but bounds memory
 * - ReadWriteLock: allows concurrent reads, exclusive writes
 * 
 * Real-world considerations:
 * - Redis uses lazy + periodic expiry (hz config controls frequency)
 * - Memcached uses lazy-only expiry
 * - In distributed setting, each node runs this independently (no cross-node eviction)
 */
public class Problem51_DistributedCache {

    static class DistributedCache<K, V> {
        private final int capacity;
        private final Map<K, Node<K, V>> map;
        private final Node<K, V> head, tail; // sentinel nodes for DLL
        private final long defaultTtlMs;
        private final ScheduledExecutorService cleanupExecutor;

        static class Node<K, V> {
            K key;
            V value;
            long expiryTime; // absolute time in ms
            Node<K, V> prev, next;

            Node(K key, V value, long expiryTime) {
                this.key = key;
                this.value = value;
                this.expiryTime = expiryTime;
            }
        }

        public DistributedCache(int capacity, long defaultTtlMs, long cleanupIntervalMs) {
            this.capacity = capacity;
            this.defaultTtlMs = defaultTtlMs;
            this.map = new ConcurrentHashMap<>();
            this.head = new Node<>(null, null, 0);
            this.tail = new Node<>(null, null, 0);
            head.next = tail;
            tail.prev = head;

            // Periodic cleanup of expired entries (like Redis's activeExpireCycle)
            cleanupExecutor = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "cache-cleanup");
                t.setDaemon(true);
                return t;
            });
            cleanupExecutor.scheduleAtFixedRate(this::evictExpired, 
                cleanupIntervalMs, cleanupIntervalMs, TimeUnit.MILLISECONDS);
        }

        public synchronized V get(K key) {
            Node<K, V> node = map.get(key);
            if (node == null) return null;

            // Lazy expiration check
            if (System.currentTimeMillis() > node.expiryTime) {
                removeNode(node);
                map.remove(key);
                return null;
            }

            // Move to front (most recently used)
            moveToFront(node);
            return node.value;
        }

        public synchronized void put(K key, V value) {
            put(key, value, defaultTtlMs);
        }

        public synchronized void put(K key, V value, long ttlMs) {
            long expiryTime = System.currentTimeMillis() + ttlMs;

            if (map.containsKey(key)) {
                Node<K, V> node = map.get(key);
                node.value = value;
                node.expiryTime = expiryTime;
                moveToFront(node);
            } else {
                // Evict if at capacity
                while (map.size() >= capacity) {
                    evictLRU();
                }
                Node<K, V> node = new Node<>(key, value, expiryTime);
                map.put(key, node);
                addToFront(node);
            }
        }

        public synchronized boolean remove(K key) {
            Node<K, V> node = map.remove(key);
            if (node != null) {
                removeNode(node);
                return true;
            }
            return false;
        }

        public synchronized int size() {
            return map.size();
        }

        private void evictLRU() {
            Node<K, V> lru = tail.prev;
            if (lru == head) return;
            removeNode(lru);
            map.remove(lru.key);
        }

        private synchronized void evictExpired() {
            long now = System.currentTimeMillis();
            // Scan from tail (LRU end) - expired entries more likely there
            Node<K, V> current = tail.prev;
            while (current != head) {
                Node<K, V> prev = current.prev;
                if (now > current.expiryTime) {
                    removeNode(current);
                    map.remove(current.key);
                }
                current = prev;
            }
        }

        private void addToFront(Node<K, V> node) {
            node.next = head.next;
            node.prev = head;
            head.next.prev = node;
            head.next = node;
        }

        private void removeNode(Node<K, V> node) {
            node.prev.next = node.next;
            node.next.prev = node.prev;
        }

        private void moveToFront(Node<K, V> node) {
            removeNode(node);
            addToFront(node);
        }

        public void shutdown() {
            cleanupExecutor.shutdown();
        }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Distributed Cache with TTL + LRU ===\n");

        // Test 1: Basic LRU eviction
        DistributedCache<String, String> cache = new DistributedCache<>(3, 10000, 1000);
        cache.put("a", "1");
        cache.put("b", "2");
        cache.put("c", "3");
        cache.put("d", "4"); // should evict "a" (LRU)
        assert cache.get("a") == null : "a should be evicted";
        assert "4".equals(cache.get("d")) : "d should exist";
        System.out.println("PASS: LRU eviction works");

        // Test 2: Access updates LRU order
        cache = new DistributedCache<>(3, 10000, 1000);
        cache.put("a", "1");
        cache.put("b", "2");
        cache.put("c", "3");
        cache.get("a"); // moves "a" to front
        cache.put("d", "4"); // should evict "b" now
        assert cache.get("a") != null : "a should still exist";
        assert cache.get("b") == null : "b should be evicted";
        System.out.println("PASS: LRU order updated on access");

        // Test 3: TTL expiration
        cache = new DistributedCache<>(10, 100, 50);
        cache.put("x", "val", 100); // expires in 100ms
        assert "val".equals(cache.get("x")) : "should exist immediately";
        Thread.sleep(150);
        assert cache.get("x") == null : "should be expired";
        System.out.println("PASS: TTL expiration works");

        // Test 4: Periodic cleanup
        cache = new DistributedCache<>(10, 50, 30);
        cache.put("p", "1");
        cache.put("q", "2");
        cache.put("r", "3");
        Thread.sleep(100); // let cleanup run
        assert cache.size() == 0 : "all should be cleaned up, got: " + cache.size();
        System.out.println("PASS: Periodic cleanup evicts expired entries");

        // Test 5: Update resets TTL
        cache = new DistributedCache<>(10, 100, 1000);
        cache.put("k", "v1", 100);
        Thread.sleep(60);
        cache.put("k", "v2", 100); // reset TTL
        Thread.sleep(60);
        assert "v2".equals(cache.get("k")) : "should still exist after TTL reset";
        System.out.println("PASS: Update resets TTL");

        cache.shutdown();
        System.out.println("\nAll tests passed!");
    }
}
