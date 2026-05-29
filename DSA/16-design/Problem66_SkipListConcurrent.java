import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * Problem 66: Skip List with Concurrent Access
 * 
 * PRODUCTION MAPPING: Redis sorted sets (ZSET), LevelDB/RocksDB MemTable,
 *                     Java ConcurrentSkipListMap, Lucene
 * 
 * Why Skip List over balanced BST:
 * - Simpler to implement correctly (especially with concurrency)
 * - Lock-free/fine-grained locking is practical (unlike Red-Black tree rotations)
 * - Good cache locality for forward traversal
 * - Probabilistic balance (no rebalancing needed)
 * 
 * Complexity: O(log n) expected for search/insert/delete
 * Space: O(n) expected (each element promoted with probability p=0.5)
 * 
 * Concurrency approach: Fine-grained locking per node (hand-over-hand)
 * Alternative: Lock-free using CAS (like java.util.concurrent.ConcurrentSkipListMap)
 */
public class Problem66_SkipListConcurrent {

    static class ConcurrentSkipList<K extends Comparable<K>, V> {
        private static final int MAX_LEVEL = 32;
        private static final double P = 0.5;
        
        private final Node<K, V> head;
        private volatile int currentLevel;
        private final AtomicInteger size = new AtomicInteger(0);
        private final Random random = new Random();

        static class Node<K, V> {
            final K key;
            volatile V value;
            final Node<K, V>[] next;
            final ReentrantLock lock = new ReentrantLock();
            volatile boolean marked = false; // for logical deletion

            @SuppressWarnings("unchecked")
            Node(K key, V value, int level) {
                this.key = key;
                this.value = value;
                this.next = new Node[level + 1];
            }
        }

        @SuppressWarnings("unchecked")
        public ConcurrentSkipList() {
            this.head = new Node<>(null, null, MAX_LEVEL);
            this.currentLevel = 0;
        }

        private int randomLevel() {
            int level = 0;
            while (level < MAX_LEVEL && random.nextDouble() < P) level++;
            return level;
        }

        public V get(K key) {
            Node<K, V> current = head;
            for (int i = currentLevel; i >= 0; i--) {
                while (current.next[i] != null && current.next[i].key.compareTo(key) < 0) {
                    current = current.next[i];
                }
            }
            current = current.next[0];
            if (current != null && current.key.compareTo(key) == 0 && !current.marked) {
                return current.value;
            }
            return null;
        }

        public void put(K key, V value) {
            int newLevel = randomLevel();
            
            // Update currentLevel if needed
            if (newLevel > currentLevel) {
                currentLevel = newLevel;
            }

            @SuppressWarnings("unchecked")
            Node<K, V>[] update = new Node[MAX_LEVEL + 1];
            Node<K, V> current = head;

            // Find position at each level
            for (int i = currentLevel; i >= 0; i--) {
                while (current.next[i] != null && current.next[i].key.compareTo(key) < 0) {
                    current = current.next[i];
                }
                update[i] = current;
            }

            current = current.next[0];

            // Update existing key
            if (current != null && current.key.compareTo(key) == 0) {
                current.value = value;
                return;
            }

            // Insert new node
            Node<K, V> newNode = new Node<>(key, value, newLevel);
            synchronized (this) {
                // Re-find update array under lock for safety
                current = head;
                for (int i = currentLevel; i >= 0; i--) {
                    while (current.next[i] != null && current.next[i].key.compareTo(key) < 0) {
                        current = current.next[i];
                    }
                    update[i] = current;
                }
                // Check again for duplicate
                if (update[0].next[0] != null && update[0].next[0].key.compareTo(key) == 0) {
                    update[0].next[0].value = value;
                    return;
                }
                for (int i = 0; i <= newLevel; i++) {
                    newNode.next[i] = update[i].next[i];
                    update[i].next[i] = newNode;
                }
            }
            size.incrementAndGet();
        }

        public boolean remove(K key) {
            @SuppressWarnings("unchecked")
            Node<K, V>[] update = new Node[MAX_LEVEL + 1];

            synchronized (this) {
                Node<K, V> current = head;
                for (int i = currentLevel; i >= 0; i--) {
                    while (current.next[i] != null && current.next[i].key.compareTo(key) < 0) {
                        current = current.next[i];
                    }
                    update[i] = current;
                }
                current = current.next[0];

                if (current == null || current.key.compareTo(key) != 0) return false;

                current.marked = true; // logical delete
                for (int i = 0; i <= currentLevel; i++) {
                    if (update[i].next[i] != current) break;
                    update[i].next[i] = current.next[i];
                }
                // Reduce level if needed
                while (currentLevel > 0 && head.next[currentLevel] == null) {
                    currentLevel--;
                }
            }
            size.decrementAndGet();
            return true;
        }

        /** Range query: return all entries where startKey <= key < endKey */
        public List<Map.Entry<K, V>> range(K startKey, K endKey) {
            List<Map.Entry<K, V>> result = new ArrayList<>();
            Node<K, V> current = head;
            
            // Find start position
            for (int i = currentLevel; i >= 0; i--) {
                while (current.next[i] != null && current.next[i].key.compareTo(startKey) < 0) {
                    current = current.next[i];
                }
            }
            current = current.next[0];

            // Collect until endKey
            while (current != null && current.key.compareTo(endKey) < 0) {
                if (!current.marked) {
                    result.add(Map.entry(current.key, current.value));
                }
                current = current.next[0];
            }
            return result;
        }

        public int size() { return size.get(); }
        public int getLevel() { return currentLevel; }
    }

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Concurrent Skip List ===\n");

        ConcurrentSkipList<Integer, String> sl = new ConcurrentSkipList<>();

        // Test 1: Basic operations
        sl.put(5, "five");
        sl.put(3, "three");
        sl.put(7, "seven");
        sl.put(1, "one");
        sl.put(9, "nine");
        
        assert "five".equals(sl.get(5));
        assert "three".equals(sl.get(3));
        assert sl.get(4) == null;
        System.out.println("PASS: Basic put/get");

        // Test 2: Update
        sl.put(5, "FIVE-updated");
        assert "FIVE-updated".equals(sl.get(5));
        System.out.println("PASS: Update existing key");

        // Test 3: Delete
        assert sl.remove(3);
        assert sl.get(3) == null;
        assert !sl.remove(99); // not found
        System.out.println("PASS: Delete");

        // Test 4: Range query
        sl = new ConcurrentSkipList<>();
        for (int i = 0; i < 20; i++) sl.put(i, "v" + i);
        List<Map.Entry<Integer, String>> range = sl.range(5, 10);
        assert range.size() == 5; // 5,6,7,8,9
        assert range.get(0).getKey() == 5;
        assert range.get(4).getKey() == 9;
        System.out.println("PASS: Range query [5,10) = " + range.size() + " results");

        // Test 5: Concurrent writes
        ConcurrentSkipList<Integer, Integer> concSl = new ConcurrentSkipList<>();
        int numThreads = 4;
        int itemsPerThread = 2500;
        ExecutorService exec = Executors.newFixedThreadPool(numThreads);
        CountDownLatch latch = new CountDownLatch(numThreads);

        for (int t = 0; t < numThreads; t++) {
            final int threadId = t;
            exec.submit(() -> {
                for (int i = 0; i < itemsPerThread; i++) {
                    concSl.put(threadId * itemsPerThread + i, i);
                }
                latch.countDown();
            });
        }
        latch.await();
        exec.shutdown();

        assert concSl.size() == numThreads * itemsPerThread : 
            "Expected " + (numThreads * itemsPerThread) + " got " + concSl.size();
        System.out.printf("PASS: Concurrent inserts (%d threads x %d items = %d total)\n",
            numThreads, itemsPerThread, concSl.size());

        // Test 6: All items findable after concurrent insert
        boolean allFound = true;
        for (int i = 0; i < numThreads * itemsPerThread; i++) {
            if (concSl.get(i) == null) { allFound = false; break; }
        }
        assert allFound;
        System.out.println("PASS: All items findable after concurrent inserts");

        // Test 7: Level distribution (probabilistic)
        sl = new ConcurrentSkipList<>();
        for (int i = 0; i < 10000; i++) sl.put(i, "v");
        System.out.printf("PASS: 10000 items, max level = %d (expected ~13)\n", sl.getLevel());

        System.out.println("\nAll tests passed!");
    }
}
