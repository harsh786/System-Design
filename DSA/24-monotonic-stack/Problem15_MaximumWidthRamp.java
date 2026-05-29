import java.util.*;

/**
 * Problem 15: Maximum Width Ramp (LeetCode 962)
 * 
 * Find maximum j - i such that nums[i] <= nums[j].
 * 
 * Approach: Build decreasing stack of candidates for i (left endpoints).
 * Then scan from right trying to match with stack elements.
 * 
 * Monotonic Invariant: Decreasing stack ensures we consider only useful left endpoints.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the longest duration between a low-load start
 * and a high-load end in capacity planning.
 */
public class Problem15_MaximumWidthRamp {
    
    public int maxWidthRamp(int[] nums) {
        int n = nums.length;
        Deque<Integer> stack = new ArrayDeque<>();
        
        // Build decreasing stack of left candidates
        for (int i = 0; i < n; i++) {
            if (stack.isEmpty() || nums[stack.peek()] > nums[i]) {
                stack.push(i);
            }
        }
        
        int maxWidth = 0;
        for (int j = n - 1; j >= 0; j--) {
            while (!stack.isEmpty() && nums[stack.peek()] <= nums[j]) {
                maxWidth = Math.max(maxWidth, j - stack.pop());
            }
        }
        return maxWidth;
    }
    
    public static void main(String[] args) {
        Problem15_MaximumWidthRamp sol = new Problem15_MaximumWidthRamp();
        
        System.out.println(sol.maxWidthRamp(new int[]{6,0,8,2,1,5})); // 4
        System.out.println(sol.maxWidthRamp(new int[]{9,8,1,0,1,9,4,0,4,1})); // 7
        System.out.println(sol.maxWidthRamp(new int[]{1,2,3})); // 2
        System.out.println(sol.maxWidthRamp(new int[]{3,2,1})); // 0
    }
}
