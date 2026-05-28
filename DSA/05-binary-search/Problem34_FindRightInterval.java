import java.util.*;

/**
 * Problem 34: Find Right Interval
 * 
 * For each interval, find the interval whose start >= current end (minimum such start).
 * 
 * Approach: Sort starts with original indices, binary search for each interval's end.
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: For each task completion time, finding the next available
 * scheduled task in a job queue — successor scheduling.
 */
public class Problem34_FindRightInterval {
    public static int[] findRightInterval(int[][] intervals) {
        int n = intervals.length;
        int[][] starts = new int[n][2]; // [start, originalIndex]
        for (int i = 0; i < n; i++) starts[i] = new int[]{intervals[i][0], i};
        Arrays.sort(starts, (a, b) -> a[0] - b[0]);
        
        int[] result = new int[n];
        for (int i = 0; i < n; i++) {
            int target = intervals[i][1];
            int lo = 0, hi = n - 1, ans = -1;
            while (lo <= hi) {
                int mid = lo + (hi - lo) / 2;
                if (starts[mid][0] >= target) { ans = starts[mid][1]; hi = mid - 1; }
                else lo = mid + 1;
            }
            result[i] = ans;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(findRightInterval(new int[][]{{1,2}})));             // [-1]
        System.out.println(Arrays.toString(findRightInterval(new int[][]{{3,4},{2,3},{1,2}}))); // [-1,0,1]
        System.out.println(Arrays.toString(findRightInterval(new int[][]{{1,4},{2,3},{3,4}}))); // [2,2,-1] or similar
    }
}
