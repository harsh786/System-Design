import java.util.*;

public class Problem35_InsertIntervalWithOrderedSet {
    // LC 57 variation: Insert interval using TreeMap
    public static int[][] insert(int[][] intervals, int[] newInterval) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int[] iv : intervals) map.put(iv[0], iv[1]);
        int start = newInterval[0], end = newInterval[1];
        Integer lo = map.floorKey(end);
        while (lo != null && map.get(lo) >= start) {
            start = Math.min(start, lo);
            end = Math.max(end, map.get(lo));
            map.remove(lo);
            lo = map.floorKey(end);
        }
        map.put(start, end);
        int[][] res = new int[map.size()][2];
        int i = 0;
        for (var e : map.entrySet()) res[i++] = new int[]{e.getKey(), e.getValue()};
        return res;
    }

    public static void main(String[] args) {
        int[][] res = insert(new int[][]{{1,3},{6,9}}, new int[]{2,5});
        for (int[] r : res) System.out.println(Arrays.toString(r));
    }
}
