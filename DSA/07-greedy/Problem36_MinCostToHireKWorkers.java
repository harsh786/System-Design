/**
 * Problem 36: Minimum Cost to Hire K Workers (LeetCode 857)
 *
 * Greedy Choice: Sort by wage/quality ratio. For each ratio as the paying ratio,
 * pick k workers with smallest quality (to minimize cost).
 *
 * Time: O(n log n), Space: O(n)
 *
 * Production Analogy: Hiring contractors minimizing total cost while respecting fair pay ratios.
 */
import java.util.*;
public class Problem36_MinCostToHireKWorkers {
    
    public static double mincostToHireWorkers(int[] quality, int[] wage, int k) {
        int n = quality.length;
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Arrays.sort(order, (a, b) -> Double.compare((double)wage[a]/quality[a], (double)wage[b]/quality[b]));
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Collections.reverseOrder());
        int qualitySum = 0;
        double minCost = Double.MAX_VALUE;
        for (int i : order) {
            maxHeap.offer(quality[i]);
            qualitySum += quality[i];
            if (maxHeap.size() > k) qualitySum -= maxHeap.poll();
            if (maxHeap.size() == k)
                minCost = Math.min(minCost, qualitySum * ((double)wage[i] / quality[i]));
        }
        return minCost;
    }
    
    public static void main(String[] args) {
        System.out.printf("%.5f%n", mincostToHireWorkers(new int[]{10,20,5}, new int[]{70,50,30}, 2)); // 105.00000
        System.out.printf("%.5f%n", mincostToHireWorkers(new int[]{3,1,10,10,1}, new int[]{4,8,2,2,7}, 3)); // 30.66667
    }
}
