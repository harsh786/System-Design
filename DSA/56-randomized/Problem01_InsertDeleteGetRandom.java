import java.util.*;

public class Problem01_InsertDeleteGetRandom {
    // O(1) Insert, Delete, GetRandom using HashMap + ArrayList
    static class RandomizedSet {
        Map<Integer, Integer> map; // val -> index
        List<Integer> list;
        Random rand;

        public RandomizedSet() {
            map = new HashMap<>();
            list = new ArrayList<>();
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
        System.out.println(rs.insert(1));  // true
        System.out.println(rs.remove(2));  // false
        System.out.println(rs.insert(2));  // true
        System.out.println(rs.getRandom()); // 1 or 2
        System.out.println(rs.remove(1));  // true
        System.out.println(rs.getRandom()); // 2
    }
}
