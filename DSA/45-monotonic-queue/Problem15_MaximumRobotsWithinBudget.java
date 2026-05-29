/**
 * Problem: Maximum Robots Within Budget (LC 2398)
 * Sliding window + monotonic deque for max charge + prefix sum for running cost.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Maximize fleet size within budget considering peak and running costs.
 */
import java.util.*;

public class Problem15_MaximumRobotsWithinBudget {
    public static int maximumRobots(int[] chargeTimes, int[] runningCosts, long budget) {
        int n = chargeTimes.length, left = 0, ans = 0;
        long sum = 0;
        Deque<Integer> deque = new ArrayDeque<>();
        for (int right = 0; right < n; right++) {
            sum += runningCosts[right];
            while (!deque.isEmpty() && chargeTimes[deque.peekLast()] <= chargeTimes[right]) deque.pollLast();
            deque.offerLast(right);
            while (!deque.isEmpty() && (long)chargeTimes[deque.peekFirst()] + (long)(right - left + 1) * sum > budget) {
                sum -= runningCosts[left];
                if (deque.peekFirst() == left) deque.pollFirst();
                left++;
            }
            ans = Math.max(ans, right - left + 1);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(maximumRobots(new int[]{3,6,1,3,4}, new int[]{2,1,3,4,5}, 25)); // 3
    }
}
