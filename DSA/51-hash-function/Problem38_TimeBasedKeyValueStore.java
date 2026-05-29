import java.util.*;

public class Problem38_TimeBasedKeyValueStore {
    private Map<String, TreeMap<Integer, String>> store = new HashMap<>();

    public void set(String key, String value, int timestamp) {
        store.computeIfAbsent(key, k -> new TreeMap<>()).put(timestamp, value);
    }

    public String get(String key, int timestamp) {
        if (!store.containsKey(key)) return "";
        Map.Entry<Integer, String> entry = store.get(key).floorEntry(timestamp);
        return entry != null ? entry.getValue() : "";
    }

    public static void main(String[] args) {
        Problem38_TimeBasedKeyValueStore sol = new Problem38_TimeBasedKeyValueStore();
        sol.set("foo", "bar", 1);
        System.out.println(sol.get("foo", 1)); // bar
        System.out.println(sol.get("foo", 3)); // bar
        sol.set("foo", "bar2", 4);
        System.out.println(sol.get("foo", 5)); // bar2
    }
}
