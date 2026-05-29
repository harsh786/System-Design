import java.util.*;

public class Problem35_LRUCacheKeyHashing {
    private int capacity;
    private LinkedHashMap<Integer, Integer> cache;

    public Problem35_LRUCacheKeyHashing(int capacity) {
        this.capacity = capacity;
        this.cache = new LinkedHashMap<>(capacity, 0.75f, true) {
            protected boolean removeEldestEntry(Map.Entry<Integer, Integer> eldest) {
                return size() > Problem35_LRUCacheKeyHashing.this.capacity;
            }
        };
    }

    public int get(int key) { return cache.getOrDefault(key, -1); }
    public void put(int key, int value) { cache.put(key, value); }

    public static void main(String[] args) {
        Problem35_LRUCacheKeyHashing lru = new Problem35_LRUCacheKeyHashing(2);
        lru.put(1, 1); lru.put(2, 2);
        System.out.println(lru.get(1)); // 1
        lru.put(3, 3);
        System.out.println(lru.get(2)); // -1
    }
}
