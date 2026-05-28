import java.util.*;

/**
 * Problem 50: Sum of Subarray Ranges (LeetCode 2104)
 * 
 * Sum of (max - min) for all subarrays.
 * 
 * Approach: Sum of subarray maximums - sum of subarray minimums.
 * Use monotonic stack for both (similar to Problem 49).
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like computing variance/range metrics across all possible
 * time windows in monitoring - measures system instability across all observation periods.
 */
public class Problem50_SumOfSubarrayRanges {

    public static long subArrayRanges(int[] nums) {
        return sumSubarrayMaxs(nums) - sumSubarrayMins(nums);
    }

    private static long sumSubarrayMins(int[] arr) {
        int n = arr.length;
        long sum = 0;
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i <= n; i++) {
            while (!stack.isEmpty() && (i == n || arr[stack.peek()] >= arr[i])) {
                int mid = stack.pop();
                int left = stack.isEmpty() ? -1 : stack.peek();
                sum += (long) arr[mid] * (mid - left) * (i - mid);
            }
            stack.push(i);
        }
        return sum;
    }

    private static long sumSubarrayMaxs(int[] arr) {
        int n = arr.length;
        long sum = 0;
        Deque<Integer> stack = new ArrayDeque<>();
        for (int i = 0; i <= n; i++) {
            while (!stack.isEmpty() && (i == n || arr[stack.peek()] <= arr[i])) {
                int mid = stack.pop();
                int left = stack.isEmpty() ? -1 : stack.peek();
                sum += (long) arr[mid] * (mid - left) * (i - mid);
            }
            stack.push(i);
        }
        return sum;
    }

    public static void main(String[] args) {
        System.out.println(subArrayRanges(new int[]{1,2,3}));   // 4
        System.out.println(subArrayRanges(new int[]{1,3,3}));   // 4
        System.out.println(subArrayRanges(new int[]{4,-2,-3,4,1})); // 59
    }
}
