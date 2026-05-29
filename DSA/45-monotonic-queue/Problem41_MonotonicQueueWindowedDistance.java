/**
 * Problem: Problem41 MonotonicQueueWindowedDistance - Find max distance (max-min) in sliding window.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Find max distance (max-min) in sliding window.
 */
import java.util.*;

public class Problem41_MonotonicQueueWindowedDistance {
    public static int[] maxDistance(int[] nums, int k) {
        int n = nums.length;
        int[] result = new int[n - k + 1];
        Deque<Integer> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            while (!maxD.isEmpty() && nums[maxD.peekLast()] <= nums[i]) maxD.pollLast();
            while (!minD.isEmpty() && nums[minD.peekLast()] >= nums[i]) minD.pollLast();
            maxD.offerLast(i); minD.offerLast(i);
            if (maxD.peekFirst() <= i - k) maxD.pollFirst();
            if (minD.peekFirst() <= i - k) minD.pollFirst();
            if (i >= k - 1) result[i - k + 1] = nums[maxD.peekFirst()] - nums[minD.peekFirst()];
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(maxDistance(new int[]{1, 5, 2, 8, 3, 4}, 3))); // [4,6,6,5]
    }
}
