import java.util.*;

/**
 * Problem 22: Maximum Performance of a Team (LeetCode 1383)
 * 
 * Approach: Sort by efficiency descending. For each engineer as min-efficiency,
 * maintain top-K speeds using min-heap.
 * 
 * Time Complexity: O(N log N + N log K)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Team composition optimization - maximizing throughput (sum of speeds)
 * * minimum SLA (efficiency) when selecting K engineers for a project.
 */
public class Problem22_MaxPerformanceOfTeam {
    
    public int maxPerformance(int n, int[] speed, int[] efficiency, int k) {
        int[][] eng = new int[n][2];
        for (int i = 0; i < n; i++) eng[i] = new int[]{efficiency[i], speed[i]};
        Arrays.sort(eng, (a, b) -> b[0] - a[0]);
        
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        long speedSum = 0, maxPerf = 0;
        
        for (int[] e : eng) {
            minHeap.offer(e[1]);
            speedSum += e[1];
            if (minHeap.size() > k) speedSum -= minHeap.poll();
            maxPerf = Math.max(maxPerf, speedSum * e[0]);
        }
        return (int)(maxPerf % 1_000_000_007);
    }
    
    public static void main(String[] args) {
        Problem22_MaxPerformanceOfTeam sol = new Problem22_MaxPerformanceOfTeam();
        System.out.println(sol.maxPerformance(6, new int[]{2,10,3,1,5,8}, new int[]{5,4,3,9,7,2}, 2)); // 60
        System.out.println(sol.maxPerformance(6, new int[]{2,10,3,1,5,8}, new int[]{5,4,3,9,7,2}, 3)); // 68
    }
}
