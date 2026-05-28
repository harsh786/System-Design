import java.util.*;

/**
 * Problem 34: Total Cost to Hire K Workers (LeetCode 2462)
 * 
 * Approach: Two min-heaps for left and right candidates windows. Pick cheapest from either side.
 * 
 * Time Complexity: O((K + candidates) * log(candidates))
 * Space Complexity: O(candidates)
 * 
 * Production Analogy: Hiring pipeline optimization - selecting cheapest candidates
 * from two sourcing channels (referrals vs job boards).
 */
public class Problem34_TotalCostToHireKWorkers {
    
    public long totalCost(int[] costs, int k, int candidates) {
        int n = costs.length;
        PriorityQueue<Integer> left = new PriorityQueue<>();
        PriorityQueue<Integer> right = new PriorityQueue<>();
        int l = 0, r = n - 1;
        
        for (int i = 0; i < candidates && l <= r; i++) left.offer(costs[l++]);
        for (int i = 0; i < candidates && l <= r; i++) right.offer(costs[r--]);
        
        long total = 0;
        for (int i = 0; i < k; i++) {
            int leftVal = left.isEmpty() ? Integer.MAX_VALUE : left.peek();
            int rightVal = right.isEmpty() ? Integer.MAX_VALUE : right.peek();
            
            if (leftVal <= rightVal) {
                total += left.poll();
                if (l <= r) left.offer(costs[l++]);
            } else {
                total += right.poll();
                if (l <= r) right.offer(costs[r--]);
            }
        }
        return total;
    }
    
    public static void main(String[] args) {
        Problem34_TotalCostToHireKWorkers sol = new Problem34_TotalCostToHireKWorkers();
        System.out.println(sol.totalCost(new int[]{17,12,10,2,7,2,11,20,8}, 3, 4)); // 11
        System.out.println(sol.totalCost(new int[]{1,2,4,1}, 3, 3)); // 4
    }
}
