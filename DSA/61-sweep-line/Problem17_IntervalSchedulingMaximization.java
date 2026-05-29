import java.util.*;

public class Problem17_IntervalSchedulingMaximization {
    public int maxNonOverlapping(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[1] - b[1]);
        int count = 0, end = Integer.MIN_VALUE;
        for (int[] intv : intervals) {
            if (intv[0] >= end) { count++; end = intv[1]; }
        }
        return count;
    }

    public static void main(String[] args) {
        Problem17_IntervalSchedulingMaximization sol = new Problem17_IntervalSchedulingMaximization();
        System.out.println(sol.maxNonOverlapping(new int[][]{{1,3},{2,4},{3,5},{0,6},{5,7},{8,9},{5,9}})); // 4
    }
}
