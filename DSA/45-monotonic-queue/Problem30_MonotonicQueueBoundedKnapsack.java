/**
 * Problem: Problem30 MonotonicQueueBoundedKnapsack - Bounded knapsack optimization using monotonic deque on grouped states.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Bounded knapsack optimization using monotonic deque on grouped states.
 */
import java.util.*;

public class Problem30_MonotonicQueueBoundedKnapsack {
    // Bounded knapsack: items with weight w, value v, count c. Capacity W.
    // Group by weight and use monotonic deque on residue classes.
    public static int boundedKnapsack(int[] weights, int[] values, int[] counts, int W) {
        int n = weights.length;
        int[] dp = new int[W + 1];
        for (int i = 0; i < n; i++) {
            int w = weights[i], v = values[i], c = counts[i];
            if (w == 0) continue;
            for (int r = 0; r < w; r++) {
                Deque<int[]> deque = new ArrayDeque<>(); // [value adjusted, index]
                int cnt = 0;
                for (int j = r; j <= W; j += w, cnt++) {
                    int val = dp[j] - cnt * v;
                    while (!deque.isEmpty() && deque.peekLast()[0] <= val) deque.pollLast();
                    deque.offerLast(new int[]{val, cnt});
                    while (deque.peekFirst()[1] < cnt - c) deque.pollFirst();
                    dp[j] = deque.peekFirst()[0] + cnt * v;
                }
            }
        }
        return dp[W];
    }

    public static void main(String[] args) {
        System.out.println(boundedKnapsack(new int[]{2, 3, 4}, new int[]{3, 4, 5}, new int[]{3, 2, 1}, 10)); // 13
    }
}
