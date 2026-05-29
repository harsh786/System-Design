import java.util.*;

public class Problem16_MaximumOverlap {
    public int maxOverlap(int[][] intervals) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (int[] intv : intervals) { map.merge(intv[0], 1, Integer::sum); map.merge(intv[1], -1, Integer::sum); }
        int max = 0, cur = 0;
        for (int v : map.values()) { cur += v; max = Math.max(max, cur); }
        return max;
    }

    public static void main(String[] args) {
        Problem16_MaximumOverlap sol = new Problem16_MaximumOverlap();
        System.out.println(sol.maxOverlap(new int[][]{{1,5},{2,6},{3,7},{4,8}})); // 4
    }
}
