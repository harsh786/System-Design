import java.util.*;

/**
 * Problem 1: Merge Intervals
 * 
 * Given an array of intervals where intervals[i] = [starti, endi], merge all overlapping intervals.
 * 
 * Approach: Sort intervals by start time, then iterate and merge overlapping ones.
 * Time Complexity: O(n log n) for sorting
 * Space Complexity: O(n) for output
 * Stability: Stable (using Arrays.sort which is TimSort)
 * 
 * Production Analogy: Calendar systems merging overlapping meetings into blocks,
 * or CDN cache invalidation merging overlapping byte ranges into single range requests.
 */
public class Problem01_MergeIntervals {
    
    public int[][] merge(int[][] intervals) {
        if (intervals == null || intervals.length <= 1) return intervals;
        
        // Sort by start time
        Arrays.sort(intervals, (a, b) -> Integer.compare(a[0], b[0]));
        
        List<int[]> merged = new ArrayList<>();
        int[] current = intervals[0];
        merged.add(current);
        
        for (int i = 1; i < intervals.length; i++) {
            if (intervals[i][0] <= current[1]) {
                // Overlapping - extend end
                current[1] = Math.max(current[1], intervals[i][1]);
            } else {
                // Non-overlapping - add new interval
                current = intervals[i];
                merged.add(current);
            }
        }
        
        return merged.toArray(new int[merged.size()][]);
    }
    
    public static void main(String[] args) {
        Problem01_MergeIntervals sol = new Problem01_MergeIntervals();
        
        // Test 1: Basic overlap
        int[][] t1 = {{1,3},{2,6},{8,10},{15,18}};
        System.out.println("Test 1: " + Arrays.deepToString(sol.merge(t1))); // [[1,6],[8,10],[15,18]]
        
        // Test 2: Full overlap
        int[][] t2 = {{1,4},{4,5}};
        System.out.println("Test 2: " + Arrays.deepToString(sol.merge(t2))); // [[1,5]]
        
        // Test 3: Single interval
        int[][] t3 = {{1,1}};
        System.out.println("Test 3: " + Arrays.deepToString(sol.merge(t3))); // [[1,1]]
        
        // Test 4: All overlapping
        int[][] t4 = {{1,10},{2,3},{4,5},{6,7}};
        System.out.println("Test 4: " + Arrays.deepToString(sol.merge(t4))); // [[1,10]]
        
        // Test 5: No overlapping
        int[][] t5 = {{1,2},{3,4},{5,6}};
        System.out.println("Test 5: " + Arrays.deepToString(sol.merge(t5))); // [[1,2],[3,4],[5,6]]
    }
}
