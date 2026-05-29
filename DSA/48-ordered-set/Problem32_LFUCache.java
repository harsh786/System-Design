import java.util.*;

public class Problem32_LFUCache {
    // LC 460: Least Frequently Used Cache
    int capacity, minFreq;
    Map<Integer, Integer> valMap;
    Map<Integer, Integer> freqMap;
    Map<Integer, LinkedHashSet<Integer>> freqToKeys;

    public Problem32_LFUCache(int capacity) {
        this.capacity = capacity;
        valMap = new HashMap<>();
        freqMap = new HashMap<>();
        freqToKeys = new HashMap<>();
    }

    public int get(int key) {
        if (!valMap.containsKey(key)) return -1;
        increaseFreq(key);
        return valMap.get(key);
    }

    public void put(int key, int value) {
        if (capacity == 0) return;
        if (valMap.containsKey(key)) { valMap.put(key, value); increaseFreq(key); return; }
        if (valMap.size() >= capacity) {
            int evict = freqToKeys.get(minFreq).iterator().next();
            freqToKeys.get(minFreq).remove(evict);
            valMap.remove(evict); freqMap.remove(evict);
        }
        valMap.put(key, value); freqMap.put(key, 1); minFreq = 1;
        freqToKeys.computeIfAbsent(1, k -> new LinkedHashSet<>()).add(key);
    }

    private void increaseFreq(int key) {
        int f = freqMap.get(key);
        freqMap.put(key, f + 1);
        freqToKeys.get(f).remove(key);
        if (freqToKeys.get(f).isEmpty()) { freqToKeys.remove(f); if (minFreq == f) minFreq++; }
        freqToKeys.computeIfAbsent(f + 1, k -> new LinkedHashSet<>()).add(key);
    }

    public static void main(String[] args) {
        Problem32_LFUCache cache = new Problem32_LFUCache(2);
        cache.put(1, 1); cache.put(2, 2);
        System.out.println(cache.get(1)); // 1
        cache.put(3, 3);
        System.out.println(cache.get(2)); // -1
        System.out.println(cache.get(3)); // 3
    }
}
