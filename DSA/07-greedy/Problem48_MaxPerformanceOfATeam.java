/**
 * Problem 48: Maximum Performance of a Team (LeetCode 1383)
 *
 * Greedy Choice: Sort by efficiency desc. For each engineer as min efficiency,
 * pick top-k speeds seen so far using min-heap.
 *
 * Time: O(n log n), Space: O(k)
 *
 * Production Analogy: Building a team where performance = total throughput * min SLA guarantee.
 */
import java.util.*;
public class Problem48_MaxPerformanceOfATeam {
    
    public static int maxPerformance(int n, int[] speed, int[] efficiency, int k) {
        int MOD = 1_000_000_007;
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Arrays.sort(order, (a, b) -> efficiency[b] - efficiency[a]);
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        long speedSum = 0, maxPerf = 0;
        for (int i : order) {
            minHeap.offer(speed[i]);
            speedSum += speed[i];
            if (minHeap.size() > k) speedSum -= minHeap.poll();
            maxPerf = Math.max(maxPerf, speedSum * efficiency[i]);
        }
        return (int)(maxPerf % MOD);
    }
    
    public static void main(String[] args) {
        System.out.println(maxPerformance(6, new int[]{2,10,3,1,5,8}, new int[]{5,4,3,9,7,2}, 2)); // 60
        System.out.println(maxPerformance(6, new int[]{2,10,3,1,5,8}, new int[]{5,4,3,9,7,2}, 3)); // 68
    }
}
