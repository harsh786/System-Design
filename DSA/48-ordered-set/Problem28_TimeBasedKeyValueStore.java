import java.util.*;

public class Problem28_TimeBasedKeyValueStore {
    // LC 981: Set with timestamp, get value at or before timestamp
    Map<String, TreeMap<Integer, String>> map;

    public Problem28_TimeBasedKeyValueStore() { map = new HashMap<>(); }

    public void set(String key, String value, int timestamp) {
        map.computeIfAbsent(key, k -> new TreeMap<>()).put(timestamp, value);
    }

    public String get(String key, int timestamp) {
        TreeMap<Integer, String> tm = map.get(key);
        if (tm == null) return "";
        Integer k = tm.floorKey(timestamp);
        return k == null ? "" : tm.get(k);
    }

    public static void main(String[] args) {
        Problem28_TimeBasedKeyValueStore store = new Problem28_TimeBasedKeyValueStore();
        store.set("foo", "bar", 1);
        System.out.println(store.get("foo", 1)); // bar
        System.out.println(store.get("foo", 3)); // bar
        store.set("foo", "bar2", 4);
        System.out.println(store.get("foo", 4)); // bar2
        System.out.println(store.get("foo", 5)); // bar2
    }
}
