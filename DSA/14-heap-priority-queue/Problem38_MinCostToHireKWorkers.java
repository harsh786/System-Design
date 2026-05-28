import java.util.*;

/**
 * Problem 38: Minimum Cost to Hire K Workers (LeetCode 857)
 * 
 * Approach: Sort by wage/quality ratio. Use max-heap to maintain K smallest qualities.
 * Cost = ratio * sum(qualities).
 * 
 * Time Complexity: O(N log N + N log K)
 * Space Complexity: O(N)
 * 
 * Production Analogy: Cloud resource procurement - minimizing total cost when each
 * resource has a minimum price-per-unit requirement.
 */
public class Problem38_MinCostToHireKWorkers {
    
    public double mincostToHireWorkers(int[] quality, int[] wage, int k) {
        int n = quality.length;
        double[][] workers = new double[n][2]; // [ratio, quality]
        for (int i = 0; i < n; i++) workers[i] = new double[]{(double)wage[i]/quality[i], quality[i]};
        Arrays.sort(workers, (a, b) -> Double.compare(a[0], b[0]));
        
        PriorityQueue<Double> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        double qualitySum = 0, minCost = Double.MAX_VALUE;
        
        for (double[] w : workers) {
            maxHeap.offer(w[1]);
            qualitySum += w[1];
            if (maxHeap.size() > k) qualitySum -= maxHeap.poll();
            if (maxHeap.size() == k) minCost = Math.min(minCost, qualitySum * w[0]);
        }
        return minCost;
    }
    
    public static void main(String[] args) {
        Problem38_MinCostToHireKWorkers sol = new Problem38_MinCostToHireKWorkers();
        System.out.printf("%.5f%n", sol.mincostToHireWorkers(new int[]{10,20,5}, new int[]{70,50,30}, 2)); // 105.0
        System.out.printf("%.5f%n", sol.mincostToHireWorkers(new int[]{3,1,10,10,1}, new int[]{4,8,2,2,7}, 3)); // 30.66667
    }
}
