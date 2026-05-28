import java.util.*;

/**
 * Problem 27: Non-overlapping Intervals
 * Find minimum number of intervals to remove to make rest non-overlapping.
 * 
 * Production Analogy: Like resolving scheduling conflicts - remove minimum meetings
 * to eliminate all overlaps (greedy by earliest end time).
 * 
 * O(n log n) time, O(1) space - greedy, sort by end time
 */
public class Problem27_NonOverlappingIntervals {

    public static int eraseOverlapIntervals(int[][] intervals) {
        if (intervals.length == 0) return 0;
        Arrays.sort(intervals, (a, b) -> a[1] - b[1]);
        int count = 0, end = intervals[0][1];
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] < end) count++;
            else end = intervals[i][1];
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(eraseOverlapIntervals(new int[][]{{1,2},{2,3},{3,4},{1,3}})); // 1
        System.out.println(eraseOverlapIntervals(new int[][]{{1,2},{1,2},{1,2}}));       // 2
        System.out.println(eraseOverlapIntervals(new int[][]{{1,2},{2,3}}));             // 0
    }
}
