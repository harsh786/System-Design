import java.util.*;

/**
 * Problem 32: Randomized Set (same as Problem 15 but standalone class name)
 * Insert, remove, getRandom all O(1). No duplicates allowed.
 *
 * Time Complexity: O(1) all operations
 * Space Complexity: O(n)
 *
 * Production Analogy: A/B test user assignment pool - randomly assign users to groups,
 * add/remove users efficiently.
 */
public class Problem32_RandomizedSet {
    private List<Integer> list = new ArrayList<>();
    private Map<Integer, Integer> map = new HashMap<>();
    private Random rand = new Random();

    public boolean insert(int val) {
        if (map.containsKey(val)) return false;
        map.put(val, list.size());
        list.add(val);
        return true;
    }

    public boolean remove(int val) {
        if (!map.containsKey(val)) return false;
        int idx = map.get(val), last = list.get(list.size()-1);
        list.set(idx, last);
        map.put(last, idx);
        list.remove(list.size()-1);
        map.remove(val);
        return true;
    }

    public int getRandom() { return list.get(rand.nextInt(list.size())); }

    public static void main(String[] args) {
        Problem32_RandomizedSet s = new Problem32_RandomizedSet();
        System.out.println(s.insert(1)); // true
        System.out.println(s.insert(2)); // true
        System.out.println(s.insert(1)); // false
        System.out.println(s.remove(1)); // true
        System.out.println(s.getRandom()); // 2
    }
}
