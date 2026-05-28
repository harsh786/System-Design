import java.util.*;

/**
 * Problem 39: Find Right Interval (LeetCode 436)
 * 
 * Approach: Two min-heaps - one sorted by start, one by end. For each ending interval,
 * find the smallest start >= end.
 * 
 * Time Complexity: O(N log N)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Job dependency scheduling - finding the next available task
 * that can start after the current one completes.
 */
public class Problem39_FindRightInterval {
    
    public int[] findRightInterval(int[][] intervals) {
        int n = intervals.length;
        // [start, index]
        PriorityQueue<int[]> starts = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        // [end, index]
        PriorityQueue<int[]> ends = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        
        for (int i = 0; i < n; i++) {
            starts.offer(new int[]{intervals[i][0], i});
            ends.offer(new int[]{intervals[i][1], i});
        }
        
        int[] result = new int[n];
        Arrays.fill(result, -1);
        
        while (!ends.isEmpty()) {
            int[] end = ends.poll();
            while (!starts.isEmpty() && starts.peek()[0] < end[0]) starts.poll();
            if (!starts.isEmpty()) result[end[1]] = starts.peek()[1];
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem39_FindRightInterval sol = new Problem39_FindRightInterval();
        System.out.println(Arrays.toString(sol.findRightInterval(new int[][]{{1,2}}))); // [-1]
        System.out.println(Arrays.toString(sol.findRightInterval(new int[][]{{3,4},{2,3},{1,2}}))); // [-1,0,1]
        System.out.println(Arrays.toString(sol.findRightInterval(new int[][]{{1,4},{2,3},{3,4}}))); // [-1,2,-1]
    }
}
