import java.util.*;

public class Problem28_RandomizedCacheEviction {
    // Random eviction cache - simpler than LRU, used in Redis
    Map<Integer, Integer> cache;
    List<Integer> keys;
    int capacity;
    Random rand = new Random();

    public Problem28_RandomizedCacheEviction(int cap) { capacity = cap; cache = new HashMap<>(); keys = new ArrayList<>(); }

    public void put(int key, int val) {
        if (cache.containsKey(key)) { cache.put(key, val); return; }
        if (cache.size() >= capacity) {
            int idx = rand.nextInt(keys.size());
            int evict = keys.get(idx);
            keys.set(idx, keys.get(keys.size()-1));
            keys.remove(keys.size()-1);
            cache.remove(evict);
        }
        cache.put(key, val);
        keys.add(key);
    }

    public int get(int key) { return cache.getOrDefault(key, -1); }

    public static void main(String[] args) {
        Problem28_RandomizedCacheEviction c = new Problem28_RandomizedCacheEviction(3);
        c.put(1,1); c.put(2,2); c.put(3,3); c.put(4,4);
        System.out.println(c.get(1) + " " + c.get(4)); // one might be evicted
    }
}
