import java.util.*;

public class Problem07_NonOverlappingIntervals {
    public int eraseOverlapIntervals(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[1] - b[1]);
        int count = 0, end = Integer.MIN_VALUE;
        for (int[] intv : intervals) {
            if (intv[0] >= end) end = intv[1];
            else count++;
        }
        return count;
    }

    public static void main(String[] args) {
        Problem07_NonOverlappingIntervals sol = new Problem07_NonOverlappingIntervals();
        System.out.println(sol.eraseOverlapIntervals(new int[][]{{1,2},{2,3},{3,4},{1,3}})); // 1
    }
}
