import java.util.*;

public class Problem36_LFUCacheKeyHashing {
    private int capacity, minFreq;
    private Map<Integer, Integer> values = new HashMap<>();
    private Map<Integer, Integer> freqs = new HashMap<>();
    private Map<Integer, LinkedHashSet<Integer>> freqKeys = new HashMap<>();

    public Problem36_LFUCacheKeyHashing(int capacity) { this.capacity = capacity; }

    public int get(int key) {
        if (!values.containsKey(key)) return -1;
        touch(key);
        return values.get(key);
    }

    public void put(int key, int value) {
        if (capacity <= 0) return;
        if (values.containsKey(key)) { values.put(key, value); touch(key); return; }
        if (values.size() >= capacity) {
            int evict = freqKeys.get(minFreq).iterator().next();
            freqKeys.get(minFreq).remove(evict);
            values.remove(evict); freqs.remove(evict);
        }
        values.put(key, value); freqs.put(key, 1); minFreq = 1;
        freqKeys.computeIfAbsent(1, k -> new LinkedHashSet<>()).add(key);
    }

    private void touch(int key) {
        int f = freqs.get(key);
        freqs.put(key, f + 1);
        freqKeys.get(f).remove(key);
        if (freqKeys.get(f).isEmpty() && f == minFreq) minFreq++;
        freqKeys.computeIfAbsent(f + 1, k -> new LinkedHashSet<>()).add(key);
    }

    public static void main(String[] args) {
        Problem36_LFUCacheKeyHashing lfu = new Problem36_LFUCacheKeyHashing(2);
        lfu.put(1, 1); lfu.put(2, 2);
        System.out.println(lfu.get(1)); // 1
        lfu.put(3, 3);
        System.out.println(lfu.get(2)); // -1
    }
}
