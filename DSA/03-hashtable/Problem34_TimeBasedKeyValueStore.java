import java.util.*;

/**
 * Problem 34: Time Based Key-Value Store
 * Store key-value pairs with timestamps. Get returns value at largest timestamp <= given timestamp.
 *
 * Approach: HashMap<key, TreeMap<timestamp, value>>. Use floorKey for lookup.
 * Alternative: HashMap<key, List<(timestamp, value)>> with binary search (since timestamps are increasing).
 *
 * Time Complexity: O(log n) for get, O(1) for set
 * Space Complexity: O(n)
 *
 * Production Analogy: Like a time-series database (InfluxDB, TimescaleDB).
 * Querying the state of a metric at a given point in time.
 */
public class Problem34_TimeBasedKeyValueStore {
    private Map<String, TreeMap<Integer, String>> store = new HashMap<>();

    public void set(String key, String value, int timestamp) {
        store.computeIfAbsent(key, k -> new TreeMap<>()).put(timestamp, value);
    }

    public String get(String key, int timestamp) {
        if (!store.containsKey(key)) return "";
        Integer t = store.get(key).floorKey(timestamp);
        return t == null ? "" : store.get(key).get(t);
    }

    public static void main(String[] args) {
        Problem34_TimeBasedKeyValueStore kv = new Problem34_TimeBasedKeyValueStore();
        kv.set("foo", "bar", 1);
        System.out.println(kv.get("foo", 1)); // "bar"
        System.out.println(kv.get("foo", 3)); // "bar"
        kv.set("foo", "bar2", 4);
        System.out.println(kv.get("foo", 4)); // "bar2"
        System.out.println(kv.get("foo", 5)); // "bar2"
        System.out.println(kv.get("foo", 0)); // ""
    }
}
