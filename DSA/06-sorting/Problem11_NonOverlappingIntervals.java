import java.util.*;

/**
 * Problem 11: Non-overlapping Intervals
 * 
 * Find minimum number of intervals to remove to make the rest non-overlapping.
 * 
 * Approach: Sort by end time. Greedily keep intervals that end earliest (activity selection).
 * Time Complexity: O(n log n)
 * Space Complexity: O(1)
 * 
 * Production Analogy: Scheduling batch jobs on a shared resource - minimize job cancellations
 * to maximize non-conflicting job throughput.
 */
public class Problem11_NonOverlappingIntervals {
    
    public int eraseOverlapIntervals(int[][] intervals) {
        if (intervals.length <= 1) return 0;
        Arrays.sort(intervals, (a, b) -> Integer.compare(a[1], b[1]));
        
        int kept = 1, end = intervals[0][1];
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] >= end) {
                kept++;
                end = intervals[i][1];
            }
        }
        return intervals.length - kept;
    }
    
    public static void main(String[] args) {
        Problem11_NonOverlappingIntervals sol = new Problem11_NonOverlappingIntervals();
        
        System.out.println("Test 1: " + sol.eraseOverlapIntervals(new int[][]{{1,2},{2,3},{3,4},{1,3}})); // 1
        System.out.println("Test 2: " + sol.eraseOverlapIntervals(new int[][]{{1,2},{1,2},{1,2}})); // 2
        System.out.println("Test 3: " + sol.eraseOverlapIntervals(new int[][]{{1,2},{2,3}})); // 0
        System.out.println("Test 4: " + sol.eraseOverlapIntervals(new int[][]{{-52,31},{-73,-26},{82,97},{-65,-11},{-62,-49},{95,99},{58,95},{-31,49},{66,98},{-63,2},{30,47},{-40,-26}})); // 7
    }
}
