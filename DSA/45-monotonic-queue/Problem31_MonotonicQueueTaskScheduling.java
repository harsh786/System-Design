/**
 * Problem: Problem31 MonotonicQueueTaskScheduling - Schedule tasks minimizing max wait using deque for window optimization.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Schedule tasks minimizing max wait using deque for window optimization.
 */
import java.util.*;

public class Problem31_MonotonicQueueTaskScheduling {
    // Minimize max waiting time: assign tasks to time slots, use deque to find optimal slot
    public static int minMaxWait(int[] arrivals, int[] durations, int k) {
        int n = arrivals.length;
        int[] dp = new int[n]; // earliest finish time
        Deque<Integer> deque = new ArrayDeque<>();
        dp[0] = arrivals[0] + durations[0];
        deque.offerLast(0);
        int maxWait = 0;
        for (int i = 1; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() < i - k) deque.pollFirst();
            int startTime = Math.max(arrivals[i], dp[deque.peekFirst()]);
            dp[i] = startTime + durations[i];
            maxWait = Math.max(maxWait, startTime - arrivals[i]);
            while (!deque.isEmpty() && dp[deque.peekLast()] >= dp[i]) deque.pollLast();
            deque.offerLast(i);
        }
        return maxWait;
    }

    public static void main(String[] args) {
        System.out.println(minMaxWait(new int[]{0, 1, 3, 5}, new int[]{2, 3, 1, 2}, 2));
    }
}
