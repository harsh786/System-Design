import java.util.*;

/**
 * Problem 49: Sum of Subarray Minimums (LeetCode 907)
 * 
 * Find sum of min(subarray) for all subarrays. Return mod 10^9+7.
 * 
 * Approach: For each element, find how many subarrays it's the minimum of.
 * Use monotonic stack to find previous less element (PLE) and next less element (NLE).
 * Contribution of arr[i] = arr[i] * left[i] * right[i].
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like computing aggregate SLA metrics - for each bottleneck service,
 * determine how many request paths it constrains (is the minimum throughput).
 */
public class Problem49_SumOfSubarrayMinimums {

    public static int sumSubarrayMins(int[] arr) {
        int MOD = 1_000_000_007;
        int n = arr.length;
        int[] left = new int[n];  // distance to previous less element
        int[] right = new int[n]; // distance to next less or equal element
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

        long sum = 0;
        for (int i = 0; i < n; i++) {
            sum = (sum + (long) arr[i] * left[i] % MOD * right[i]) % MOD;
        }
        return (int) sum;
    }

    public static void main(String[] args) {
        System.out.println(sumSubarrayMins(new int[]{3,1,2,4})); // 17
        System.out.println(sumSubarrayMins(new int[]{11,81,94,43,3})); // 444
    }
}
