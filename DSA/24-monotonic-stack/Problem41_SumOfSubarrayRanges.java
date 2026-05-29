import java.util.*;

/**
 * Problem 41: Sum of Subarray Ranges (LeetCode 2104)
 * 
 * Sum of (max - min) for all subarrays = sum of max - sum of min.
 * Use monotonic stack for both sum of subarray maximums and minimums.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Measuring total volatility across all time windows -
 * used in risk assessment.
 */
public class Problem41_SumOfSubarrayRanges {
    
    public long subArrayRanges(int[] nums) {
        return sumOfMaximums(nums) - sumOfMinimums(nums);
    }
    
    private long sumOfMinimums(int[] nums) {
        int n = nums.length;
        int[] left = new int[n], right = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && nums[stack.peek()] >= nums[i]) stack.pop();
            left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && nums[stack.peek()] > nums[i]) stack.pop();
            right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
            stack.push(i);
        }
        long sum = 0;
        for (int i = 0; i < n; i++) sum += (long) nums[i] * left[i] * right[i];
        return sum;
    }
    
    private long sumOfMaximums(int[] nums) {
        int n = nums.length;
        int[] left = new int[n], right = new int[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && nums[stack.peek()] <= nums[i]) stack.pop();
            left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && nums[stack.peek()] < nums[i]) stack.pop();
            right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
            stack.push(i);
        }
        long sum = 0;
        for (int i = 0; i < n; i++) sum += (long) nums[i] * left[i] * right[i];
        return sum;
    }
    
    public static void main(String[] args) {
        Problem41_SumOfSubarrayRanges sol = new Problem41_SumOfSubarrayRanges();
        System.out.println(sol.subArrayRanges(new int[]{1,2,3}));   // 4
        System.out.println(sol.subArrayRanges(new int[]{1,3,3}));   // 4
        System.out.println(sol.subArrayRanges(new int[]{4,-2,-3,4,1})); // 59
    }
}
