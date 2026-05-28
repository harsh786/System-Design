import java.util.*;

/**
 * Problem 26: Insert Interval
 * Insert a new interval into sorted non-overlapping intervals, merging if needed.
 * 
 * Production Analogy: Like inserting a new maintenance window into an existing schedule -
 * merge with any overlapping windows.
 * 
 * O(n) time, O(n) space
 */
public class Problem26_InsertInterval {

    public static int[][] insert(int[][] intervals, int[] newInterval) {
        List<int[]> result = new ArrayList<>();
        int i = 0, n = intervals.length;
        while (i < n && intervals[i][1] < newInterval[0]) result.add(intervals[i++]);
        while (i < n && intervals[i][0] <= newInterval[1]) {
            newInterval[0] = Math.min(newInterval[0], intervals[i][0]);
            newInterval[1] = Math.max(newInterval[1], intervals[i][1]);
            i++;
        }
        result.add(newInterval);
        while (i < n) result.add(intervals[i++]);
        return result.toArray(new int[0][]);
    }

    public static void main(String[] args) {
        System.out.println(Arrays.deepToString(insert(new int[][]{{1,3},{6,9}}, new int[]{2,5}))); // [[1,5],[6,9]]
        System.out.println(Arrays.deepToString(insert(new int[][]{{1,2},{3,5},{6,7},{8,10},{12,16}}, new int[]{4,8}))); // [[1,2],[3,10],[12,16]]
    }
}
