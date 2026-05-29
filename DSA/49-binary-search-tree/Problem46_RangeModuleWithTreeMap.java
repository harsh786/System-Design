import java.util.*;

public class Problem46_RangeModuleWithTreeMap {
    TreeMap<Integer, Integer> map = new TreeMap<>();

    public void addRange(int left, int right) {
        Integer s = map.floorKey(left), e = map.floorKey(right);
        if (s != null && map.get(s) >= left) left = s;
        if (e != null && map.get(e) > right) right = map.get(e);
        map.subMap(left, right).clear();
        map.put(left, right);
    }

    public boolean queryRange(int left, int right) {
        Integer s = map.floorKey(left);
        return s != null && map.get(s) >= right;
    }

    public void removeRange(int left, int right) {
        Integer s = map.floorKey(left), e = map.floorKey(right);
        if (e != null && map.get(e) > right) map.put(right, map.get(e));
        if (s != null && map.get(s) > left) map.put(s, left);
        map.subMap(left, true, right, false).clear();
    }

    public static void main(String[] args) {
        Problem46_RangeModuleWithTreeMap rm = new Problem46_RangeModuleWithTreeMap();
        rm.addRange(10, 20);
        System.out.println(rm.queryRange(10, 14)); // true
        rm.removeRange(14, 16);
        System.out.println(rm.queryRange(13, 15)); // false
    }
}
