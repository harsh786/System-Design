import java.util.*;

/**
 * Problem 30: Range Module
 * 
 * API Contract:
 * - addRange(left, right): Track [left, right)
 * - queryRange(left, right): Return true if entire [left, right) is tracked
 * - removeRange(left, right): Stop tracking [left, right)
 * 
 * Complexity: O(log n) for query, O(n) worst for add/remove (merging intervals)
 * Data Structure: TreeMap<Integer, Integer> representing merged intervals
 * 
 * Production Analogy: IP range blocking, memory allocator free-list management,
 * time slot booking systems, firewall rules
 */
public class Problem30_RangeModule {

    static class RangeModule {
        private TreeMap<Integer, Integer> map; // start -> end

        public RangeModule() { map = new TreeMap<>(); }

        public void addRange(int left, int right) {
            Integer start = map.floorKey(left);
            Integer end = map.floorKey(right);
            if (start != null && map.get(start) >= left) left = start;
            if (end != null && map.get(end) > right) right = map.get(end);
            map.subMap(left, right).clear();
            map.put(left, right);
        }

        public boolean queryRange(int left, int right) {
            Integer start = map.floorKey(left);
            return start != null && map.get(start) >= right;
        }

        public void removeRange(int left, int right) {
            Integer start = map.floorKey(left);
            Integer end = map.floorKey(right);
            if (end != null && map.get(end) > right) map.put(right, map.get(end));
            if (start != null && map.get(start) > left) map.put(start, left);
            map.subMap(left, true, right, false).clear();
        }
    }

    public static void main(String[] args) {
        RangeModule rm = new RangeModule();
        rm.addRange(10, 20);
        rm.removeRange(14, 16);
        assert rm.queryRange(10, 14);
        assert !rm.queryRange(13, 15);
        assert rm.queryRange(16, 17);
        rm.addRange(14, 16);
        assert rm.queryRange(10, 20);

        System.out.println("All tests passed!");
    }
}
