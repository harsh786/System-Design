import java.util.*;

/**
 * Problem 13: Time Based Key-Value Store
 * 
 * Set values with timestamps, get the value at or before a given timestamp.
 * 
 * Approach: Store list of (timestamp, value) per key. Binary search for
 * the largest timestamp <= given timestamp.
 * 
 * Time: set O(1), get O(log n), Space: O(n)
 * 
 * Production Analogy: A versioned configuration store (like etcd) where you
 * query "what was the config at time T?" — point-in-time reads.
 */
public class Problem13_TimeBasedKeyValueStore {
    private Map<String, List<int[]>> timeMap; // value encoded as index into vals
    private Map<String, List<String>> valMap;

    public Problem13_TimeBasedKeyValueStore() {
        timeMap = new HashMap<>();
        valMap = new HashMap<>();
    }

    public void set(String key, String value, int timestamp) {
        timeMap.computeIfAbsent(key, k -> new ArrayList<>()).add(new int[]{timestamp});
        valMap.computeIfAbsent(key, k -> new ArrayList<>()).add(value);
    }

    public String get(String key, int timestamp) {
        if (!timeMap.containsKey(key)) return "";
        List<int[]> times = timeMap.get(key);
        List<String> vals = valMap.get(key);
        // Binary search for rightmost time <= timestamp
        int lo = 0, hi = times.size() - 1, result = -1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (times.get(mid)[0] <= timestamp) { result = mid; lo = mid + 1; }
            else hi = mid - 1;
        }
        return result == -1 ? "" : vals.get(result);
    }

    public static void main(String[] args) {
        Problem13_TimeBasedKeyValueStore store = new Problem13_TimeBasedKeyValueStore();
        store.set("foo", "bar", 1);
        System.out.println(store.get("foo", 1));  // bar
        System.out.println(store.get("foo", 3));  // bar
        store.set("foo", "bar2", 4);
        System.out.println(store.get("foo", 4));  // bar2
        System.out.println(store.get("foo", 5));  // bar2
        System.out.println(store.get("foo", 0));  // ""
        System.out.println(store.get("baz", 1));  // ""
    }
}
