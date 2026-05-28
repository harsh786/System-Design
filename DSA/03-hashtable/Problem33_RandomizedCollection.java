import java.util.*;

/**
 * Problem 33: Randomized Collection (Insert Delete GetRandom O(1) - Duplicates allowed)
 * Same as RandomizedSet but allows duplicates. getRandom returns proportional to count.
 *
 * Approach: Map val -> Set of indices. List stores values.
 *
 * Time Complexity: O(1) average all operations
 * Space Complexity: O(n)
 *
 * Production Analogy: Weighted random selection from a pool (e.g., weighted load balancing
 * where servers appear multiple times proportional to their capacity).
 */
public class Problem33_RandomizedCollection {
    private List<Integer> list = new ArrayList<>();
    private Map<Integer, Set<Integer>> map = new HashMap<>();
    private Random rand = new Random();

    public boolean insert(int val) {
        map.computeIfAbsent(val, k -> new LinkedHashSet<>()).add(list.size());
        list.add(val);
        return map.get(val).size() == 1;
    }

    public boolean remove(int val) {
        if (!map.containsKey(val) || map.get(val).isEmpty()) return false;
        int removeIdx = map.get(val).iterator().next();
        map.get(val).remove(removeIdx);
        int lastIdx = list.size() - 1;
        int lastVal = list.get(lastIdx);
        if (removeIdx != lastIdx) {
            list.set(removeIdx, lastVal);
            map.get(lastVal).remove(lastIdx);
            map.get(lastVal).add(removeIdx);
        }
        list.remove(lastIdx);
        if (map.get(val).isEmpty()) map.remove(val);
        return true;
    }

    public int getRandom() { return list.get(rand.nextInt(list.size())); }

    public static void main(String[] args) {
        Problem33_RandomizedCollection c = new Problem33_RandomizedCollection();
        System.out.println(c.insert(1)); // true
        System.out.println(c.insert(1)); // false
        System.out.println(c.insert(2)); // true
        System.out.println(c.getRandom()); // 1 or 2 (1 twice as likely)
        System.out.println(c.remove(1)); // true
        System.out.println(c.getRandom()); // 1 or 2
    }
}
