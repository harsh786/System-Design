package segmenttree;

import java.util.*;

/**
 * Problem 27: Minimum Interval to Include Each Query (LeetCode 1851)
 * 
 * Approach: Offline processing with sweep. Sort intervals by size, sort queries.
 * Use segment tree or simply a sorted structure. Here we use offline + priority queue approach
 * but demonstrate segment tree concept.
 * 
 * Time Complexity: O((n+q) log(n+q))
 * Space Complexity: O(n+q)
 */
public class Problem27_MinimumIntervalToIncludeEachQuery {
    
    public int[] minInterval(int[][] intervals, int[] queries) {
        int q = queries.length;
        int[][] sortedQ = new int[q][2];
        for (int i = 0; i < q; i++) { sortedQ[i][0] = queries[i]; sortedQ[i][1] = i; }
        Arrays.sort(sortedQ, (a, b) -> a[0] - b[0]);
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]);
        
        // Min-heap by interval size
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> (a[1] - a[0]) - (b[1] - b[0]));
        int[] ans = new int[q];
        Arrays.fill(ans, -1);
        int j = 0;
        for (int[] sq : sortedQ) {
            int point = sq[0], idx = sq[1];
            while (j < intervals.length && intervals[j][0] <= point) { pq.offer(intervals[j]); j++; }
            while (!pq.isEmpty() && pq.peek()[1] < point) pq.poll();
            if (!pq.isEmpty()) ans[idx] = pq.peek()[1] - pq.peek()[0] + 1;
        }
        return ans;
    }
    
    public static void main(String[] args) {
        Problem27_MinimumIntervalToIncludeEachQuery sol = new Problem27_MinimumIntervalToIncludeEachQuery();
        int[] res = sol.minInterval(new int[][]{{1,4},{2,4},{3,6},{4,4}}, new int[]{2,3,4,5});
        System.out.println(Arrays.toString(res)); // [3,3,1,4]
    }
}
