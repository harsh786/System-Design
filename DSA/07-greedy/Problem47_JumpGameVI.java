/**
 * Problem 47: Jump Game VI (LeetCode 1696)
 *
 * Greedy/DP with monotone deque: At each position, pick max score within last k positions.
 *
 * Time: O(n), Space: O(n)
 *
 * Production Analogy: Maximum throughput path with sliding window connection reuse.
 */
import java.util.*;
public class Problem47_JumpGameVI {
    
    public static int maxResult(int[] nums, int k) {
        int n = nums.length;
        int[] dp = new int[n];
        dp[0] = nums[0];
        Deque<Integer> dq = new ArrayDeque<>();
        dq.offer(0);
        for (int i = 1; i < n; i++) {
            while (!dq.isEmpty() && dq.peekFirst() < i - k) dq.pollFirst();
            dp[i] = dp[dq.peekFirst()] + nums[i];
            while (!dq.isEmpty() && dp[dq.peekLast()] <= dp[i]) dq.pollLast();
            dq.offerLast(i);
        }
        return dp[n - 1];
    }
    
    public static void main(String[] args) {
        System.out.println(maxResult(new int[]{1,-1,-2,4,-7,3}, 2));  // 7
        System.out.println(maxResult(new int[]{10,-5,-2,4,0,3}, 3)); // 17
        System.out.println(maxResult(new int[]{1,-5,-20,4,-1,3,-6,-3}, 2)); // 0
    }
}
