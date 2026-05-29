import java.util.*;

public class Problem21_LongestCoveredInterval {
    public int longestCovered(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        int maxLen = 0, start = intervals[0][0], end = intervals[0][1];
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] <= end) { end = Math.max(end, intervals[i][1]); }
            else { maxLen = Math.max(maxLen, end - start); start = intervals[i][0]; end = intervals[i][1]; }
        }
        return Math.max(maxLen, end - start);
    }

    public static void main(String[] args) {
        Problem21_LongestCoveredInterval sol = new Problem21_LongestCoveredInterval();
        System.out.println(sol.longestCovered(new int[][]{{1,4},{2,6},{8,10},{9,12}})); // 5
    }
}
