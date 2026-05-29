/**
 * Problem: Problem27 MonotonicQueueJumpGame - Can reach end with max jump k, maximize score using deque DP.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Can reach end with max jump k, maximize score using deque DP.
 */
import java.util.*;

public class Problem27_MonotonicQueueJumpGame {
    public static int maxScoreJump(int[] nums, int k) {
        int n = nums.length;
        int[] dp = new int[n];
        dp[0] = nums[0];
        Deque<Integer> deque = new ArrayDeque<>();
        deque.offerLast(0);
        for (int i = 1; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() < i - k) deque.pollFirst();
            dp[i] = nums[i] + dp[deque.peekFirst()];
            while (!deque.isEmpty() && dp[deque.peekLast()] <= dp[i]) deque.pollLast();
            deque.offerLast(i);
        }
        return dp[n - 1];
    }

    public static void main(String[] args) {
        System.out.println(maxScoreJump(new int[]{1, -1, -2, 4, -7, 3}, 2)); // 7
    }
}
