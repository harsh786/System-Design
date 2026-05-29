import java.util.*;

/**
 * Problem 9: 132 Pattern (LeetCode 456)
 * 
 * Find if there exists i < j < k such that nums[i] < nums[k] < nums[j].
 * 
 * Approach: Traverse from right. Maintain decreasing stack for potential nums[j].
 * Track the last popped value as nums[k] (the "2" in 132).
 * If any element < nums[k], we found our "1".
 * 
 * Monotonic Invariant: Decreasing stack from right. Popped elements represent
 * valid "2" candidates bounded by their "3".
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Anomaly detection - finding a dip-spike-partial_dip pattern
 * in service latency metrics.
 */
public class Problem09_132Pattern {
    
    public boolean find132pattern(int[] nums) {
        int n = nums.length;
        Deque<Integer> stack = new ArrayDeque<>();
        int third = Integer.MIN_VALUE; // the "2" in 132 pattern
        
        for (int i = n - 1; i >= 0; i--) {
            if (nums[i] < third) return true;
            while (!stack.isEmpty() && nums[i] > stack.peek()) {
                third = stack.pop();
            }
            stack.push(nums[i]);
        }
        return false;
    }
    
    public static void main(String[] args) {
        Problem09_132Pattern sol = new Problem09_132Pattern();
        
        System.out.println(sol.find132pattern(new int[]{1,2,3,4}));    // false
        System.out.println(sol.find132pattern(new int[]{3,1,4,2}));    // true
        System.out.println(sol.find132pattern(new int[]{-1,3,2,0}));   // true
        System.out.println(sol.find132pattern(new int[]{1,0,1,-4,3})); // false? actually true: [1,0,1,-4,3] -> -4,3,? no. [-4,3,?] no. Actually false.
        System.out.println(sol.find132pattern(new int[]{3,5,0,3,4}));  // true
    }
}
