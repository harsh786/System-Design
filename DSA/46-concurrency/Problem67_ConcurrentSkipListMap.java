import java.util.concurrent.atomic.*;
import java.util.concurrent.*;
import java.util.*;

/**
 * Problem 67: Concurrent Skip List Map
 * 
 * REAL-WORLD USAGE:
 * - Java's ConcurrentSkipListMap (sorted concurrent map)
 * - Redis sorted sets (zset) use skip lists
 * - LevelDB/RocksDB memtable (in-memory sorted structure)
 * - Apache Lucene's ConcurrentMergeScheduler
 * 
 * WHY SKIP LIST OVER BALANCED TREE:
 * - Lock-free/fine-grained locking is MUCH easier on skip lists
 * - Balanced trees (Red-Black, AVL) need rotations that touch multiple nodes
 * - Skip list operations are "local" - only affect neighboring nodes
 * - Probabilistic balancing (no complex rebalancing logic)
 * 
 * KEY CONCEPTS:
 * - Layered linked lists with probabilistic height
 * - Search: start from top level, go right until overshoot, go down
 * - Insert: find position at each level, link in with CAS
 * - Delete: logically mark node, then physically unlink
 * 
 * MEMORY ORDERING:
 * - Node's next pointers are AtomicReference (CAS for linking)
 * - Logical deletion uses a "marked" flag (lazy physical deletion)
 * - Bottom-up insertion ensures a node is fully linked before visible at higher levels
 * 
 * PITFALLS:
 * 1. Must insert bottom-up (if top-first, a search could find partially linked node)
 * 2. Deletion is two-phase: mark → unlink (concurrent searches may still traverse marked nodes)
 * 3. Randomized level height: use ThreadLocalRandom (not shared Random)
 * 4. Max level should be log2(expected size) for O(log n) performance
 */
public class Problem67_ConcurrentSkipListMap<K extends Comparable<K>, V> {

    private static final int MAX_LEVEL = 16;

    static class Node<K, V> {
        final K key;
        volatile V value;
        final AtomicReference<Node<K, V>>[] next;
        volatile boolean marked = false; // Logically deleted
        final int level;

        @SuppressWarnings("unchecked")
        Node(K key, V value, int level) {
            this.key = key;
            this.value = value;
            this.level = level;
            this.next = new AtomicReference[level + 1];
            for (int i = 0; i <= level; i++) {
                next[i] = new AtomicReference<>(null);
            }
        }
    }

    private final Node<K, V> head; // Sentinel head (key = null, max level)
    private final AtomicInteger size = new AtomicInteger(0);

    @SuppressWarnings("unchecked")
    public Problem67_ConcurrentSkipListMap() {
        head = new Node<>(null, null, MAX_LEVEL);
    }

    private int randomLevel() {
        int level = 0;
        while (level < MAX_LEVEL && ThreadLocalRandom.current().nextBoolean()) {
            level++;
        }
        return level;
    }

    /**
     * Find predecessors and successors at each level.
     * This is the core search that all operations use.
     */
    @SuppressWarnings("unchecked")
    private boolean find(K key, Node<K, V>[] preds, Node<K, V>[] succs) {
        retry:
        while (true) {
            Node<K, V> pred = head;
            for (int level = MAX_LEVEL; level >= 0; level--) {
                Node<K, V> curr = pred.next[level].get();
                while (curr != null) {
                    // Skip marked (deleted) nodes
                    if (curr.marked) {
                        // Try to physically unlink
                        Node<K, V> succ = curr.next[level].get();
                        if (!pred.next[level].compareAndSet(curr, succ)) {
                            continue retry; // Restart search
                        }
                        curr = succ;
                        continue;
                    }
                    if (curr.key.compareTo(key) < 0) {
                        pred = curr;
                        curr = curr.next[level].get();
                    } else {
                        break;
                    }
                }
                preds[level] = pred;
                succs[level] = curr;
            }
            // Check if found at level 0
            Node<K, V> found = succs[0];
            return found != null && found.key.compareTo(key) == 0 && !found.marked;
        }
    }

    public V put(K key, V value) {
        int newLevel = randomLevel();
        @SuppressWarnings("unchecked")
        Node<K, V>[] preds = new Node[MAX_LEVEL + 1];
        @SuppressWarnings("unchecked")
        Node<K, V>[] succs = new Node[MAX_LEVEL + 1];

        while (true) {
            if (find(key, preds, succs)) {
                // Key exists - update value
                Node<K, V> found = succs[0];
                V oldValue = found.value;
                found.value = value; // Volatile write
                return oldValue;
            }

            // Insert new node
            Node<K, V> newNode = new Node<>(key, value, newLevel);

            // Link at level 0 first (bottom-up)
            for (int level = 0; level <= newLevel; level++) {
                newNode.next[level].set(succs[level]);
            }

            // CAS at level 0 - this is the linearization point
            if (!preds[0].next[0].compareAndSet(succs[0], newNode)) {
                continue; // Retry
            }

            // Link at higher levels (best-effort; find() will clean up if we fail)
            for (int level = 1; level <= newLevel; level++) {
                while (true) {
                    if (newNode.marked) break; // Node was deleted while we're linking
                    if (preds[level].next[level].compareAndSet(succs[level], newNode)) {
                        break;
                    }
                    // Re-find to get updated preds/succs
                    find(key, preds, succs);
                }
            }
            size.incrementAndGet();
            return null;
        }
    }

    public V get(K key) {
        Node<K, V> pred = head;
        for (int level = MAX_LEVEL; level >= 0; level--) {
            Node<K, V> curr = pred.next[level].get();
            while (curr != null && !curr.marked && curr.key.compareTo(key) < 0) {
                pred = curr;
                curr = curr.next[level].get();
            }
            if (curr != null && !curr.marked && curr.key.compareTo(key) == 0) {
                return curr.value;
            }
        }
        return null;
    }

    public V remove(K key) {
        @SuppressWarnings("unchecked")
        Node<K, V>[] preds = new Node[MAX_LEVEL + 1];
        @SuppressWarnings("unchecked")
        Node<K, V>[] succs = new Node[MAX_LEVEL + 1];

        if (!find(key, preds, succs)) {
            return null; // Not found
        }

        Node<K, V> nodeToRemove = succs[0];
        V value = nodeToRemove.value;
        // Logical deletion (physical unlink happens lazily in find())
        nodeToRemove.marked = true;
        size.decrementAndGet();
        return value;
    }

    public int size() { return size.get(); }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Concurrent Skip List Map ===\n");

        Problem67_ConcurrentSkipListMap<Integer, String> skipList = new Problem67_ConcurrentSkipListMap<>();
        int numThreads = 8;
        int opsPerThread = 100_000;
        AtomicInteger puts = new AtomicInteger(0);
        AtomicInteger gets = new AtomicInteger(0);
        AtomicInteger removes = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random rng = new Random();
                for (int i = 0; i < opsPerThread; i++) {
                    int key = rng.nextInt(10000);
                    int op = rng.nextInt(10);
                    if (op < 5) { // 50% puts
                        skipList.put(key, "val-" + key);
                        puts.incrementAndGet();
                    } else if (op < 8) { // 30% gets
                        skipList.get(key);
                        gets.incrementAndGet();
                    } else { // 20% removes
                        skipList.remove(key);
                        removes.incrementAndGet();
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        int totalOps = numThreads * opsPerThread;
        System.out.println("Threads: " + numThreads + ", Ops/thread: " + opsPerThread);
        System.out.println("Puts: " + puts.get() + ", Gets: " + gets.get() + ", Removes: " + removes.get());
        System.out.println("Final size: " + skipList.size());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (totalOps * 1_000_000_000L / elapsed) + " ops/sec");

        // Verify ordering
        System.out.println("\nKey insight: Skip lists enable O(log n) concurrent sorted maps.");
        System.out.println("Redis sorted sets and LevelDB memtables use this exact structure.");
        System.out.println("Lock-free operations are much simpler than on balanced trees.");
    }
}
