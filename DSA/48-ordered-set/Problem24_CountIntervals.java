import java.util.*;

public class Problem24_CountIntervals {
    // LC 2276: Count total covered integers across added intervals
    TreeMap<Integer, Integer> map = new TreeMap<>();
    int count = 0;

    public void add(int left, int right) {
        Integer start = map.floorKey(right);
        while (start != null && map.get(start) >= left) {
            int end = map.get(start);
            left = Math.min(left, start);
            right = Math.max(right, end);
            count -= (end - start + 1);
            map.remove(start);
            start = map.floorKey(right);
        }
        map.put(left, right);
        count += (right - left + 1);
    }

    public int count() { return count; }

    public static void main(String[] args) {
        Problem24_CountIntervals ci = new Problem24_CountIntervals();
        ci.add(2, 3); ci.add(7, 10);
        System.out.println(ci.count()); // 6
        ci.add(5, 8);
        System.out.println(ci.count()); // 8
    }
}
