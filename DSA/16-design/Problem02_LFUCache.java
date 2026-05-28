import java.util.*;

/**
 * Problem 2: LFU Cache (Least Frequently Used)
 * 
 * API Contract:
 * - get(key): Return value, increment frequency. -1 if not found.
 * - put(key, value): Insert/update. Evict LFU (then LRU among ties) if full.
 * 
 * Complexity: O(1) for both operations
 * Data Structures: 3 HashMaps - key->value, key->freq, freq->LinkedHashSet(keys)
 * 
 * Production Analogy: CDN caching popular assets, database query plan cache,
 * DNS resolver cache with frequency-based eviction
 */
public class Problem02_LFUCache {

    static class LFUCache {
        private int capacity, minFreq;
        private Map<Integer, Integer> keyToVal;
        private Map<Integer, Integer> keyToFreq;
        private Map<Integer, LinkedHashSet<Integer>> freqToKeys;

        public LFUCache(int capacity) {
            this.capacity = capacity;
            minFreq = 0;
            keyToVal = new HashMap<>();
            keyToFreq = new HashMap<>();
            freqToKeys = new HashMap<>();
        }

        public int get(int key) {
            if (!keyToVal.containsKey(key)) return -1;
            incrementFreq(key);
            return keyToVal.get(key);
        }

        public void put(int key, int value) {
            if (capacity <= 0) return;
            if (keyToVal.containsKey(key)) {
                keyToVal.put(key, value);
                incrementFreq(key);
                return;
            }
            if (keyToVal.size() >= capacity) {
                // evict LFU, LRU among ties
                LinkedHashSet<Integer> keys = freqToKeys.get(minFreq);
                int evict = keys.iterator().next();
                keys.remove(evict);
                if (keys.isEmpty()) freqToKeys.remove(minFreq);
                keyToVal.remove(evict);
                keyToFreq.remove(evict);
            }
            keyToVal.put(key, value);
            keyToFreq.put(key, 1);
            freqToKeys.computeIfAbsent(1, k -> new LinkedHashSet<>()).add(key);
            minFreq = 1;
        }

        private void incrementFreq(int key) {
            int freq = keyToFreq.get(key);
            keyToFreq.put(key, freq + 1);
            freqToKeys.get(freq).remove(key);
            if (freqToKeys.get(freq).isEmpty()) {
                freqToKeys.remove(freq);
                if (minFreq == freq) minFreq++;
            }
            freqToKeys.computeIfAbsent(freq + 1, k -> new LinkedHashSet<>()).add(key);
        }
    }

    public static void main(String[] args) {
        LFUCache cache = new LFUCache(2);
        cache.put(1, 1);
        cache.put(2, 2);
        assert cache.get(1) == 1; // freq(1)=2, freq(2)=1
        cache.put(3, 3); // evicts key 2 (LFU)
        assert cache.get(2) == -1;
        assert cache.get(3) == 3;
        cache.put(4, 4); // evicts key 3 (freq 1, LRU among freq=1)
        assert cache.get(1) == 1;
        assert cache.get(3) == -1;
        assert cache.get(4) == 4;

        // Edge: capacity 0
        LFUCache c0 = new LFUCache(0);
        c0.put(1, 1);
        assert c0.get(1) == -1;

        System.out.println("All tests passed!");
    }
}
