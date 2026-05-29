import java.util.*;

/**
 * Problem 42: Find Right Interval
 * 
 * For each interval, find the minimum-start interval whose start >= current end.
 * 
 * Approach: Sort by start with original indices, binary search for each end.
 * Time Complexity: O(n log n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Finding the next available resource after a task completes -
 * like scheduling follow-up jobs in workflow orchestration.
 */
public class Problem42_FindRightInterval {
    
    public int[] findRightInterval(int[][] intervals) {
        int n = intervals.length;
        int[][] sorted = new int[n][2]; // [start, original_index]
        for (int i = 0; i < n; i++) sorted[i] = new int[]{intervals[i][0], i};
        Arrays.sort(sorted, (a, b) -> a[0] - b[0]);
        
        int[] result = new int[n];
        for (int i = 0; i < n; i++) {
            int target = intervals[i][1]; // end of current interval
            int lo = 0, hi = n;
            while (lo < hi) {
                int mid = lo + (hi - lo) / 2;
                if (sorted[mid][0] >= target) hi = mid;
                else lo = mid + 1;
            }
            result[i] = lo < n ? sorted[lo][1] : -1;
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem42_FindRightInterval sol = new Problem42_FindRightInterval();
        
        System.out.println("Test 1: " + Arrays.toString(sol.findRightInterval(new int[][]{{1,2}}))); // [-1]
        System.out.println("Test 2: " + Arrays.toString(sol.findRightInterval(new int[][]{{3,4},{2,3},{1,2}}))); // [-1,0,1]
        System.out.println("Test 3: " + Arrays.toString(sol.findRightInterval(new int[][]{{1,4},{2,3},{3,4}}))); // [-1,2,-1]
    }
}
