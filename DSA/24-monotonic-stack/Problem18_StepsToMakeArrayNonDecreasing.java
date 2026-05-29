import java.util.*;

/**
 * Problem 18: Steps to Make Array Non-decreasing (LeetCode 2289)
 * 
 * In each step, remove elements that are strictly less than their left neighbor.
 * Return number of steps until no more removals.
 * 
 * Approach: Process from right to left with decreasing stack.
 * Track how many steps each element survives. Answer is the max.
 * 
 * Monotonic Invariant: Decreasing stack. For each element, its "death step" depends
 * on the max death step of elements it will eventually consume.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Cascade failure propagation - how many rounds until
 * all unstable nodes are removed from a system.
 */
public class Problem18_StepsToMakeArrayNonDecreasing {
    
    public int totalSteps(int[] nums) {
        int n = nums.length;
        Deque<Integer> stack = new ArrayDeque<>();
        int[] dp = new int[n]; // steps until this element is removed
        int ans = 0;
        
        for (int i = 0; i < n; i++) {
            int cur = 0;
            while (!stack.isEmpty() && nums[stack.peek()] <= nums[i]) {
                cur = Math.max(cur, dp[stack.pop()]);
            }
            if (!stack.isEmpty()) {
                dp[i] = cur + 1;
                ans = Math.max(ans, dp[i]);
            }
            stack.push(i);
        }
        return ans;
    }
    
    public static void main(String[] args) {
        Problem18_StepsToMakeArrayNonDecreasing sol = new Problem18_StepsToMakeArrayNonDecreasing();
        
        System.out.println(sol.totalSteps(new int[]{5,3,4,4,7,3,6,11,8,5,11})); // 3
        System.out.println(sol.totalSteps(new int[]{4,5,7,7,13})); // 0
        System.out.println(sol.totalSteps(new int[]{10,1,2,3,4,5,6,1,2,3})); // 6
    }
}
