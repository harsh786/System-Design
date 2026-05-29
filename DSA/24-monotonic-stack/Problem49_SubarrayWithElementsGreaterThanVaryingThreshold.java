import java.util.*;

/**
 * Problem 49: Subarray With Elements Greater Than Varying Threshold (LeetCode 2334)
 * 
 * Find subarray of length k where every element > threshold / k.
 * Equivalently, find element where element * span > threshold (span = subarray length
 * where element is minimum).
 * 
 * Approach: For each element as minimum, check if arr[i] * span > threshold.
 * Use monotonic stack to find span (PSE and NSE).
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding a time window where minimum throughput per node
 * exceeds required QoS threshold.
 */
public class Problem49_SubarrayWithElementsGreaterThanVaryingThreshold {
    
    public int validSubarraySize(int[] nums, int threshold) {
        int n = nums.length;
        int[] left = new int[n], right = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && nums[stack.peek()] >= nums[i]) stack.pop();
            left[i] = stack.isEmpty() ? -1 : stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && nums[stack.peek()] >= nums[i]) stack.pop();
            right[i] = stack.isEmpty() ? n : stack.peek();
            stack.push(i);
        }
        
        for (int i = 0; i < n; i++) {
            int k = right[i] - left[i] - 1; // span where nums[i] is minimum
            // Need: nums[i] > threshold / k, i.e., nums[i] * k > threshold
            if ((long) nums[i] * k > threshold) return k;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        Problem49_SubarrayWithElementsGreaterThanVaryingThreshold sol = new Problem49_SubarrayWithElementsGreaterThanVaryingThreshold();
        
        System.out.println(sol.validSubarraySize(new int[]{1,3,4,3,1}, 6)); // 3
        System.out.println(sol.validSubarraySize(new int[]{6,5,6,5,8}, 7)); // 1
        System.out.println(sol.validSubarraySize(new int[]{1,2,3}, 100));   // -1
    }
}
