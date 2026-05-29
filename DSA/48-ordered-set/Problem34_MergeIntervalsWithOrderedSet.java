import java.util.*;

public class Problem34_MergeIntervalsWithOrderedSet {
    // LC 56 variation: Merge intervals using TreeMap
    public static int[][] merge(int[][] intervals) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int[] iv : intervals) {
            int start = iv[0], end = iv[1];
            Integer lo = map.floorKey(end);
            while (lo != null && map.get(lo) >= start) {
                start = Math.min(start, lo);
                end = Math.max(end, map.get(lo));
                map.remove(lo);
                lo = map.floorKey(end);
            }
            map.put(start, end);
        }
        int[][] res = new int[map.size()][2];
        int i = 0;
        for (var e : map.entrySet()) res[i++] = new int[]{e.getKey(), e.getValue()};
        return res;
    }

    public static void main(String[] args) {
        int[][] res = merge(new int[][]{{1,3},{2,6},{8,10},{15,18}});
        for (int[] r : res) System.out.println(Arrays.toString(r));
    }
}
