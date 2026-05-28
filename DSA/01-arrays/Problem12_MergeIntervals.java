import java.util.*;

/**
 * Problem 12: Merge Intervals
 * Merge all overlapping intervals.
 * 
 * Production Analogy: Like merging overlapping time windows in a scheduler -
 * consolidating maintenance windows or meeting times.
 * 
 * O(n log n) time (sorting), O(n) space for output
 */
public class Problem12_MergeIntervals {

    public static int[][] merge(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        List<int[]> merged = new ArrayList<>();
        for (int[] interval : intervals) {
            if (merged.isEmpty() || merged.get(merged.size()-1)[1] < interval[0])
                merged.add(interval);
            else
                merged.get(merged.size()-1)[1] = Math.max(merged.get(merged.size()-1)[1], interval[1]);
        }
        return merged.toArray(new int[0][]);
    }

    public static void main(String[] args) {
        System.out.println(Arrays.deepToString(merge(new int[][]{{1,3},{2,6},{8,10},{15,18}}))); // [[1,6],[8,10],[15,18]]
        System.out.println(Arrays.deepToString(merge(new int[][]{{1,4},{4,5}}))); // [[1,5]]
        System.out.println(Arrays.deepToString(merge(new int[][]{{1,4},{0,4}}))); // [[0,4]]
    }
}
