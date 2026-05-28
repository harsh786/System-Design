import java.util.*;

/**
 * Problem 4: Design HashMap
 * 
 * API Contract:
 * - put(key, value): Insert or update
 * - get(key): Return value or -1
 * - remove(key): Remove mapping
 * 
 * Complexity: O(1) average, O(n/k) worst case where k = bucket count
 * Data Structure: Array of linked lists (separate chaining)
 * 
 * Production Analogy: Core of every in-memory KV store (Redis, Memcached),
 * Java's HashMap, Python's dict implementation
 */
public class Problem04_DesignHashMap {

    static class MyHashMap {
        private static final int SIZE = 1009; // prime number for better distribution
        private LinkedList<int[]>[] buckets;

        @SuppressWarnings("unchecked")
        public MyHashMap() {
            buckets = new LinkedList[SIZE];
        }

        private int hash(int key) { return key % SIZE; }

        public void put(int key, int value) {
            int idx = hash(key);
            if (buckets[idx] == null) buckets[idx] = new LinkedList<>();
            for (int[] pair : buckets[idx]) {
                if (pair[0] == key) { pair[1] = value; return; }
            }
            buckets[idx].add(new int[]{key, value});
        }

        public int get(int key) {
            int idx = hash(key);
            if (buckets[idx] == null) return -1;
            for (int[] pair : buckets[idx]) {
                if (pair[0] == key) return pair[1];
            }
            return -1;
        }

        public void remove(int key) {
            int idx = hash(key);
            if (buckets[idx] == null) return;
            buckets[idx].removeIf(pair -> pair[0] == key);
        }
    }

    public static void main(String[] args) {
        MyHashMap map = new MyHashMap();
        map.put(1, 1);
        map.put(2, 2);
        assert map.get(1) == 1;
        assert map.get(3) == -1;
        map.put(2, 1);
        assert map.get(2) == 1;
        map.remove(2);
        assert map.get(2) == -1;

        // Collision test
        map.put(1, 10);
        map.put(1010, 20); // same bucket as 1 (1010 % 1009 = 1)
        assert map.get(1) == 10;
        assert map.get(1010) == 20;

        System.out.println("All tests passed!");
    }
}
