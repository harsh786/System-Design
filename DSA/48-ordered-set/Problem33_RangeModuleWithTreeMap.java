import java.util.*;

public class Problem33_RangeModuleWithTreeMap {
    // Variation of Range Module using TreeMap with merge on overlap
    TreeMap<Integer, Integer> intervals;

    public Problem33_RangeModuleWithTreeMap() { intervals = new TreeMap<>(); }

    public void addRange(int left, int right) {
        Integer start = intervals.floorKey(left);
        Integer end = intervals.floorKey(right);
        if (start != null && intervals.get(start) >= left) left = start;
        if (end != null && intervals.get(end) > right) right = intervals.get(end);
        intervals.subMap(left, right).clear();
        intervals.put(left, right);
    }

    public boolean queryRange(int left, int right) {
        Integer start = intervals.floorKey(left);
        return start != null && intervals.get(start) >= right;
    }

    public void removeRange(int left, int right) {
        Integer start = intervals.floorKey(left);
        Integer end = intervals.floorKey(right);
        if (end != null && intervals.get(end) > right) intervals.put(right, intervals.get(end));
        if (start != null && intervals.get(start) > left) intervals.put(start, left);
        intervals.subMap(left, true, right, false).clear();
    }

    public static void main(String[] args) {
        Problem33_RangeModuleWithTreeMap rm = new Problem33_RangeModuleWithTreeMap();
        rm.addRange(10, 20); rm.addRange(14, 16);
        System.out.println(rm.queryRange(10, 14)); // true
        rm.removeRange(14, 16);
        System.out.println(rm.queryRange(14, 16)); // false
    }
}
