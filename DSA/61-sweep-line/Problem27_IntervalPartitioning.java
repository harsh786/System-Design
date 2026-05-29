import java.util.*;

public class Problem27_IntervalPartitioning {
    /* Minimum number of groups to partition intervals so no two overlap in same group */
    public int minGroups(int[][] intervals) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] intv : intervals) { sweep.merge(intv[0], 1, Integer::sum); sweep.merge(intv[1] + 1, -1, Integer::sum); }
        int max = 0, cur = 0;
        for (int v : sweep.values()) { cur += v; max = Math.max(max, cur); }
        return max;
    }

    public static void main(String[] args) {
        Problem27_IntervalPartitioning sol = new Problem27_IntervalPartitioning();
        System.out.println(sol.minGroups(new int[][]{{1,5},{2,3},{3,6},{5,7}})); // 2
    }
}
