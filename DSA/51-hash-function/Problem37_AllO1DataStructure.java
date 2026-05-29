import java.util.*;

public class Problem37_AllO1DataStructure {
    private Map<String, Integer> keyCount = new HashMap<>();
    private TreeMap<Integer, LinkedHashSet<String>> countKeys = new TreeMap<>();

    public void inc(String key) {
        int prev = keyCount.getOrDefault(key, 0);
        keyCount.put(key, prev + 1);
        if (prev > 0) { countKeys.get(prev).remove(key); if (countKeys.get(prev).isEmpty()) countKeys.remove(prev); }
        countKeys.computeIfAbsent(prev + 1, k -> new LinkedHashSet<>()).add(key);
    }

    public void dec(String key) {
        int prev = keyCount.get(key);
        countKeys.get(prev).remove(key); if (countKeys.get(prev).isEmpty()) countKeys.remove(prev);
        if (prev == 1) keyCount.remove(key);
        else { keyCount.put(key, prev - 1); countKeys.computeIfAbsent(prev - 1, k -> new LinkedHashSet<>()).add(key); }
    }

    public String getMaxKey() { return countKeys.isEmpty() ? "" : countKeys.lastEntry().getValue().iterator().next(); }
    public String getMinKey() { return countKeys.isEmpty() ? "" : countKeys.firstEntry().getValue().iterator().next(); }

    public static void main(String[] args) {
        Problem37_AllO1DataStructure ds = new Problem37_AllO1DataStructure();
        ds.inc("hello"); ds.inc("hello"); ds.inc("world");
        System.out.println("Max: " + ds.getMaxKey()); // hello
        System.out.println("Min: " + ds.getMinKey()); // world
    }
}
