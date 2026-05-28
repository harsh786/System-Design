import java.util.*;

/**
 * Problem 15: Insert Delete GetRandom O(1)
 * Design a data structure supporting insert, remove, and getRandom in O(1).
 *
 * Approach: ArrayList for O(1) random access + HashMap(val -> index) for O(1) lookup.
 * On remove, swap with last element to maintain O(1) delete.
 *
 * Time Complexity: O(1) for all operations
 * Space Complexity: O(n)
 *
 * Production Analogy: Like a load balancer's server pool - need to add/remove servers
 * and randomly pick one for each request, all in O(1).
 */
public class Problem15_InsertDeleteGetRandomO1 {
    private List<Integer> list = new ArrayList<>();
    private Map<Integer, Integer> valToIdx = new HashMap<>();
    private Random rand = new Random();

    public boolean insert(int val) {
        if (valToIdx.containsKey(val)) return false;
        valToIdx.put(val, list.size());
        list.add(val);
        return true;
    }

    public boolean remove(int val) {
        if (!valToIdx.containsKey(val)) return false;
        int idx = valToIdx.get(val);
        int last = list.get(list.size() - 1);
        list.set(idx, last);
        valToIdx.put(last, idx);
        list.remove(list.size() - 1);
        valToIdx.remove(val);
        return true;
    }

    public int getRandom() {
        return list.get(rand.nextInt(list.size()));
    }

    public static void main(String[] args) {
        Problem15_InsertDeleteGetRandomO1 ds = new Problem15_InsertDeleteGetRandomO1();
        System.out.println(ds.insert(1)); // true
        System.out.println(ds.remove(2)); // false
        System.out.println(ds.insert(2)); // true
        System.out.println(ds.getRandom()); // 1 or 2
        System.out.println(ds.remove(1)); // true
        System.out.println(ds.insert(2)); // false (already exists)
        System.out.println(ds.getRandom()); // 2
    }
}
