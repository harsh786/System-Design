import java.util.*;

/**
 * Problem 5: Design HashSet
 * 
 * API Contract:
 * - add(key): Insert key
 * - contains(key): Check existence
 * - remove(key): Remove key
 * 
 * Complexity: O(1) average
 * Data Structure: Array of linked lists (separate chaining)
 * 
 * Production Analogy: Bloom filter backing store, deduplication systems,
 * visited URL tracking in web crawlers
 */
public class Problem05_DesignHashSet {

    static class MyHashSet {
        private static final int SIZE = 1009;
        private LinkedList<Integer>[] buckets;

        @SuppressWarnings("unchecked")
        public MyHashSet() {
            buckets = new LinkedList[SIZE];
        }

        private int hash(int key) { return key % SIZE; }

        public void add(int key) {
            int idx = hash(key);
            if (buckets[idx] == null) buckets[idx] = new LinkedList<>();
            if (!buckets[idx].contains(key)) buckets[idx].add(key);
        }

        public void remove(int key) {
            int idx = hash(key);
            if (buckets[idx] != null) buckets[idx].remove(Integer.valueOf(key));
        }

        public boolean contains(int key) {
            int idx = hash(key);
            return buckets[idx] != null && buckets[idx].contains(key);
        }
    }

    public static void main(String[] args) {
        MyHashSet set = new MyHashSet();
        set.add(1);
        set.add(2);
        assert set.contains(1);
        assert !set.contains(3);
        set.add(2);
        assert set.contains(2);
        set.remove(2);
        assert !set.contains(2);

        // Edge: remove non-existent
        set.remove(999);
        assert !set.contains(999);

        System.out.println("All tests passed!");
    }
}
