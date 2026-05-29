import java.util.*;

/**
 * Problem 44: Monotonic Stack for Contribution Counting
 * 
 * Pattern: Count each element's contribution as min/max across all subarrays.
 * Generalized template for sum-of-subarray-mins/maxs problems.
 * 
 * For each element, find:
 * - left[i]: distance to previous less/greater element
 * - right[i]: distance to next less/greater element
 * - contribution = arr[i] * left[i] * right[i]
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Billing calculation - each resource's cost contribution
 * across all possible usage windows.
 */
public class Problem44_MonotonicStackForContributionCounting {
    
    // Template: Sum of subarray minimums
    public long sumOfSubarrayMins(int[] arr) {
        int n = arr.length;
        long[] left = new long[n];
        long[] right = new long[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
            left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && arr[stack.peek()] > arr[i]) stack.pop();
            right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
            stack.push(i);
        }
        
        long total = 0;
        for (int i = 0; i < n; i++) total += (long) arr[i] * left[i] * right[i];
        return total;
    }
    
    // Template: Sum of subarray maximums
    public long sumOfSubarrayMaxs(int[] arr) {
        int n = arr.length;
        long[] left = new long[n];
        long[] right = new long[n];
        Deque<Integer> stack = new ArrayDeque<>();
        
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && arr[stack.peek()] <= arr[i]) stack.pop();
            left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
            stack.push(i);
        }
        stack.clear();
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && arr[stack.peek()] < arr[i]) stack.pop();
            right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
            stack.push(i);
        }
        
        long total = 0;
        for (int i = 0; i < n; i++) total += (long) arr[i] * left[i] * right[i];
        return total;
    }
    
    public static void main(String[] args) {
        Problem44_MonotonicStackForContributionCounting sol = new Problem44_MonotonicStackForContributionCounting();
        
        System.out.println(sol.sumOfSubarrayMins(new int[]{3,1,2,4})); // 17
        System.out.println(sol.sumOfSubarrayMaxs(new int[]{3,1,2,4})); // 30
        // Sum of ranges = 30 - 17 = 13? Let's verify: subarrays [3],[1],[2],[4],[3,1],[1,2],[2,4],[3,1,2],[1,2,4],[3,1,2,4]
        // ranges: 0,0,0,0,2,1,2,2,3,3 = 13. Correct!
        System.out.println("Sum of ranges: " + (sol.sumOfSubarrayMaxs(new int[]{3,1,2,4}) - sol.sumOfSubarrayMins(new int[]{3,1,2,4})));
    }
}
