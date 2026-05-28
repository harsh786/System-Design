import java.util.*;

/**
 * Problem 46: Minimum Interval to Include Each Query (LeetCode 1851)
 * 
 * Approach: Sort intervals by start, sort queries. For each query, add all starting
 * intervals to min-heap by size. Remove expired ones. Top = answer.
 * 
 * Time Complexity: O(N log N + Q log Q)
 * Space Complexity: O(N + Q)
 * 
 * Production Analogy: Finding the tightest SLA window that covers a given timestamp
 * for billing or compliance reporting.
 */
public class Problem46_MinIntervalToIncludeEachQuery {
    
    public int[] minInterval(int[][] intervals, int[] queries) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        int[] result = new int[queries.length];
        
        int[][] sortedQ = new int[queries.length][2];
        for (int i = 0; i < queries.length; i++) sortedQ[i] = new int[]{queries[i], i};
        Arrays.sort(sortedQ, (a, b) -> a[0] - b[0]);
        
        // [size, right]
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> a[0] - b[0]);
        int idx = 0;
        
        for (int[] q : sortedQ) {
            while (idx < intervals.length && intervals[idx][0] <= q[0]) {
                pq.offer(new int[]{intervals[idx][1] - intervals[idx][0] + 1, intervals[idx][1]});
                idx++;
            }
            while (!pq.isEmpty() && pq.peek()[1] < q[0]) pq.poll();
            result[q[1]] = pq.isEmpty() ? -1 : pq.peek()[0];
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem46_MinIntervalToIncludeEachQuery sol = new Problem46_MinIntervalToIncludeEachQuery();
        System.out.println(Arrays.toString(sol.minInterval(
            new int[][]{{1,4},{2,4},{3,6},{4,4}}, new int[]{2,3,4,5}))); // [3,3,1,4]
        System.out.println(Arrays.toString(sol.minInterval(
            new int[][]{{2,3},{2,5},{1,8},{20,25}}, new int[]{2,19,5,22}))); // [2,-1,4,6]
    }
}
