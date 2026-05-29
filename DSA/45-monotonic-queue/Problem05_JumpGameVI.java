/**
 * Problem: Jump Game VI (LC 1696)
 * DP + monotonic deque. dp[i] = nums[i] + max(dp[i-k..i-1]), deque tracks max in window.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Optimal path selection in network routing with hop constraints.
 */
import java.util.*;

public class Problem05_JumpGameVI {
    public static int maxResult(int[] nums, int k) {
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
        System.out.println(maxResult(new int[]{1,-1,-2,4,-7,3}, 2)); // 7
        System.out.println(maxResult(new int[]{10,-5,-2,4,0,3}, 3)); // 17
    }
}
