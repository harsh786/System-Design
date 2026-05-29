import java.util.*;

/**
 * Problem 9: Time Based Key-Value Store
 * 
 * API Contract:
 * - set(key, value, timestamp): Store key-value at given timestamp
 * - get(key, timestamp): Get value with largest timestamp <= given timestamp
 * 
 * Complexity: set O(1), get O(log n) via binary search
 * Data Structure: HashMap<String, TreeMap<Integer, String>> or list + binary search
 * 
 * Production Analogy: Versioned configuration systems, Git-like data stores,
 * time-series databases (InfluxDB), event sourcing stores
 */
public class Problem09_TimeBasedKeyValueStore {

    static class TimeMap {
        private Map<String, TreeMap<Integer, String>> map;

        public TimeMap() {
            map = new HashMap<>();
        }

        public void set(String key, String value, int timestamp) {
            map.computeIfAbsent(key, k -> new TreeMap<>()).put(timestamp, value);
        }

        public String get(String key, int timestamp) {
            if (!map.containsKey(key)) return "";
            TreeMap<Integer, String> tm = map.get(key);
            Integer floor = tm.floorKey(timestamp);
            return floor == null ? "" : tm.get(floor);
        }
    }

    public static void main(String[] args) {
        TimeMap tm = new TimeMap();
        tm.set("foo", "bar", 1);
        assert tm.get("foo", 1).equals("bar");
        assert tm.get("foo", 3).equals("bar");
        tm.set("foo", "bar2", 4);
        assert tm.get("foo", 4).equals("bar2");
        assert tm.get("foo", 5).equals("bar2");
        assert tm.get("foo", 3).equals("bar");

        // Edge: timestamp before any set
        assert tm.get("foo", 0).equals("");
        // Edge: non-existent key
        assert tm.get("baz", 1).equals("");

        System.out.println("All tests passed!");
    }
}
