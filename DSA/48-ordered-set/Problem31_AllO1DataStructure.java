import java.util.*;

public class Problem31_AllO1DataStructure {
    // LC 432: All O(1) - inc, dec, getMaxKey, getMinKey in O(1)
    Map<String, Integer> counts;
    TreeMap<Integer, LinkedHashSet<String>> countToKeys;

    public Problem31_AllO1DataStructure() {
        counts = new HashMap<>();
        countToKeys = new TreeMap<>();
    }

    public void inc(String key) {
        int old = counts.getOrDefault(key, 0);
        counts.put(key, old + 1);
        if (old > 0) { countToKeys.get(old).remove(key); if (countToKeys.get(old).isEmpty()) countToKeys.remove(old); }
        countToKeys.computeIfAbsent(old + 1, k -> new LinkedHashSet<>()).add(key);
    }

    public void dec(String key) {
        int old = counts.get(key);
        countToKeys.get(old).remove(key);
        if (countToKeys.get(old).isEmpty()) countToKeys.remove(old);
        if (old == 1) counts.remove(key);
        else { counts.put(key, old - 1); countToKeys.computeIfAbsent(old - 1, k -> new LinkedHashSet<>()).add(key); }
    }

    public String getMaxKey() { return countToKeys.isEmpty() ? "" : countToKeys.lastEntry().getValue().iterator().next(); }
    public String getMinKey() { return countToKeys.isEmpty() ? "" : countToKeys.firstEntry().getValue().iterator().next(); }

    public static void main(String[] args) {
        Problem31_AllO1DataStructure ds = new Problem31_AllO1DataStructure();
        ds.inc("hello"); ds.inc("hello"); ds.inc("world");
        System.out.println(ds.getMaxKey()); // hello
        System.out.println(ds.getMinKey()); // world
        ds.inc("world"); ds.inc("world");
        System.out.println(ds.getMaxKey()); // world
    }
}
