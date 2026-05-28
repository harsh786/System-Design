import java.util.*;
/**
 * Problem 35: Shortest Subarray with Sum at Least K (LeetCode 862)
 * 
 * Approach: Prefix sums + monotonic deque. Unlike Problem 7, this has negatives.
 * Window invariant: deque stores indices with increasing prefix sums.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like finding the shortest burst of network activity
 * (including drops) that exceeds a bandwidth threshold.
 */
public class Problem35_ShortestSubarrayWithSumAtLeastK {
    public static int shortestSubarray(int[] nums, int k) {
        int n = nums.length;
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];
        Deque<Integer> deque = new ArrayDeque<>();
        int minLen = n + 1;
        for (int i = 0; i <= n; i++) {
            while (!deque.isEmpty() && prefix[i] - prefix[deque.peekFirst()] >= k) {
                minLen = Math.min(minLen, i - deque.pollFirst());
            }
            while (!deque.isEmpty() && prefix[i] <= prefix[deque.peekLast()]) {
                deque.pollLast();
            }
            deque.offerLast(i);
        }
        return minLen <= n ? minLen : -1;
    }

    public static void main(String[] args) {
        System.out.println(shortestSubarray(new int[]{1}, 1));              // 1
        System.out.println(shortestSubarray(new int[]{1,2}, 4));            // -1
        System.out.println(shortestSubarray(new int[]{2,-1,2}, 3));         // 3
        System.out.println(shortestSubarray(new int[]{84,-37,32,40,95}, 167)); // 3
    }
}
