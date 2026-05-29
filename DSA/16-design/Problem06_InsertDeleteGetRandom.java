import java.util.*;

/**
 * Problem 6: Insert Delete GetRandom O(1)
 * 
 * API Contract:
 * - insert(val): Insert if not present. Return true if inserted.
 * - remove(val): Remove if present. Return true if removed.
 * - getRandom(): Return random element with equal probability.
 * 
 * Complexity: O(1) average for all operations
 * Data Structure: ArrayList + HashMap (val -> index)
 * Trick: Swap with last element for O(1) removal from array
 * 
 * Production Analogy: Load balancer random server selection,
 * A/B testing random group assignment, shuffle algorithms
 */
public class Problem06_InsertDeleteGetRandom {

    static class RandomizedSet {
        private List<Integer> list;
        private Map<Integer, Integer> map; // val -> index
        private Random rand;

        public RandomizedSet() {
            list = new ArrayList<>();
            map = new HashMap<>();
            rand = new Random();
        }

        public boolean insert(int val) {
            if (map.containsKey(val)) return false;
            map.put(val, list.size());
            list.add(val);
            return true;
        }

        public boolean remove(int val) {
            if (!map.containsKey(val)) return false;
            int idx = map.get(val);
            int last = list.get(list.size() - 1);
            list.set(idx, last);
            map.put(last, idx);
            list.remove(list.size() - 1);
            map.remove(val);
            return true;
        }

        public int getRandom() {
            return list.get(rand.nextInt(list.size()));
        }
    }

    public static void main(String[] args) {
        RandomizedSet rs = new RandomizedSet();
        assert rs.insert(1);
        assert !rs.insert(1);
        assert rs.insert(2);
        assert rs.remove(1);
        assert !rs.remove(1);
        assert rs.insert(2) == false;
        int r = rs.getRandom();
        assert r == 2;

        // Stress: insert many, remove many
        RandomizedSet rs2 = new RandomizedSet();
        for (int i = 0; i < 100; i++) rs2.insert(i);
        for (int i = 0; i < 50; i++) rs2.remove(i);
        Set<Integer> seen = new HashSet<>();
        for (int i = 0; i < 1000; i++) seen.add(rs2.getRandom());
        assert seen.size() == 50; // should see all remaining elements

        System.out.println("All tests passed!");
    }
}
