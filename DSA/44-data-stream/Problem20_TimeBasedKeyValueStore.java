import java.util.*;

public class Problem20_TimeBasedKeyValueStore {
    // 981. Time Based Key-Value Store.
    
    Map<String, TreeMap<Integer, String>> map = new HashMap<>();
    
    public void set(String key, String value, int timestamp) {
        map.computeIfAbsent(key, k -> new TreeMap<>()).put(timestamp, value);
    }
    
    public String get(String key, int timestamp) {
        TreeMap<Integer, String> tm = map.get(key);
        if (tm == null) return "";
        Integer floor = tm.floorKey(timestamp);
        return floor == null ? "" : tm.get(floor);
    }
    
    public static void main(String[] args) {
        Problem20_TimeBasedKeyValueStore sol = new Problem20_TimeBasedKeyValueStore();
        sol.set("foo", "bar", 1);
        System.out.println(sol.get("foo", 1)); // bar
        System.out.println(sol.get("foo", 3)); // bar
        sol.set("foo", "bar2", 4);
        System.out.println(sol.get("foo", 4)); // bar2
        System.out.println(sol.get("foo", 5)); // bar2
    }
}
