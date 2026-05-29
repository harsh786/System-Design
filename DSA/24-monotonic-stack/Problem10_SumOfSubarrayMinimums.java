import java.util.*;

/**
 * Problem 10: Sum of Subarray Minimums (LeetCode 907)
 * 
 * Find sum of min(subarray) for all subarrays.
 * 
 * Approach: For each element, find how many subarrays it's the minimum of.
 * Use Previous Less Element (PLE) and Next Less Element (NLE).
 * Contribution of arr[i] = arr[i] * left[i] * right[i]
 * 
 * Monotonic Invariant: Increasing stack to find PLE and NLE boundaries.
 * Handle duplicates by using strict < on one side and <= on the other.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: SLA computation - for each time window, what's the minimum
 * availability? Sum across all windows for aggregate reporting.
 */
public class Problem10_SumOfSubarrayMinimums {
    
    private static final int MOD = 1_000_000_007;
    
    public int sumSubarrayMins(int[] arr) {
        int n = arr.length;
        int[] left = new int[n];  // distance to previous less element
        int[] right = new int[n]; // distance to next less or equal element
        Deque<Integer> stack = new ArrayDeque<>();
        
        // PLE: strictly less
        for (int i = 0; i < n; i++) {
            while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
            left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
            stack.push(i);
        }
        
        stack.clear();
        // NLE: less or equal (to avoid double counting duplicates)
        for (int i = n - 1; i >= 0; i--) {
            while (!stack.isEmpty() && arr[stack.peek()] > arr[i]) stack.pop();
            right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
            stack.push(i);
        }
        
        long sum = 0;
        for (int i = 0; i < n; i++) {
            sum = (sum + (long) arr[i] * left[i] % MOD * right[i]) % MOD;
        }
        return (int) sum;
    }
    
    public static void main(String[] args) {
        Problem10_SumOfSubarrayMinimums sol = new Problem10_SumOfSubarrayMinimums();
        
        System.out.println(sol.sumSubarrayMins(new int[]{3,1,2,4}));  // 17
        System.out.println(sol.sumSubarrayMins(new int[]{11,81,94,43,3})); // 444
        System.out.println(sol.sumSubarrayMins(new int[]{1}));        // 1
        System.out.println(sol.sumSubarrayMins(new int[]{1,1,1}));    // 6
    }
}
