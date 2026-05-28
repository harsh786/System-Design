/**
 * Problem 6: Non-overlapping Intervals (LeetCode 435)
 *
 * Greedy Choice: Sort by end time, always keep interval that ends earliest.
 * Exchange Argument: Keeping earlier-ending interval leaves more room for future intervals.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Maximizing non-conflicting meeting room bookings by removing minimum conflicts.
 */
import java.util.*;
public class Problem06_NonOverlappingIntervals {
    
    public static int eraseOverlapIntervals(int[][] intervals) {
        if (intervals.length == 0) return 0;
        Arrays.sort(intervals, (a, b) -> Integer.compare(a[1], b[1]));
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
