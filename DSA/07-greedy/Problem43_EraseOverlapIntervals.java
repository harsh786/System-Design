/**
 * Problem 43: Erase Overlap Intervals (LeetCode 435) - Same as Problem 6
 *
 * Greedy Choice: Sort by end time, keep maximum non-overlapping intervals.
 * Answer = total - max_non_overlapping.
 *
 * Time: O(n log n), Space: O(1)
 *
 * Production Analogy: Minimum cancelled meetings to resolve all room conflicts.
 */
import java.util.*;
public class Problem43_EraseOverlapIntervals {
    
    public static int eraseOverlapIntervals(int[][] intervals) {
        if (intervals.length == 0) return 0;
        Arrays.sort(intervals, (a, b) -> Integer.compare(a[1], b[1]));
        int nonOverlap = 1, end = intervals[0][1];
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] >= end) {
                nonOverlap++;
                end = intervals[i][1];
            }
        }
        return intervals.length - nonOverlap;
    }
    
    public static void main(String[] args) {
        System.out.println(eraseOverlapIntervals(new int[][]{{1,2},{2,3},{3,4},{1,3}})); // 1
        System.out.println(eraseOverlapIntervals(new int[][]{{1,2},{1,2},{1,2}}));       // 2
        System.out.println(eraseOverlapIntervals(new int[][]{{1,2},{2,3}}));             // 0
    }
}
