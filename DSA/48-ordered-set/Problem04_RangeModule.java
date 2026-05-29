import java.util.*;

public class Problem04_RangeModule {
    // LC 715: Track ranges, support addRange, queryRange, removeRange
    TreeMap<Integer, Integer> map;

    public Problem04_RangeModule() {
        map = new TreeMap<>();
    }

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

    public static void main(String[] args) {
        Problem04_RangeModule rm = new Problem04_RangeModule();
        rm.addRange(10, 20);
        rm.removeRange(14, 16);
        System.out.println(rm.queryRange(10, 14)); // true
        System.out.println(rm.queryRange(13, 15)); // false
        System.out.println(rm.queryRange(16, 17)); // true
    }
}
