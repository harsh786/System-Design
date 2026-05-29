/**
 * Problem: Longest Continuous Subarray With Absolute Diff Limit (LC 1438)
 * Two deques (max/min) + sliding window. Expand right, shrink left when max-min > limit.
 * Time: O(n) | Space: O(n)
 * Production Analogy: SLA compliance - find longest period where metric variance stays within threshold.
 */
import java.util.*;

public class Problem04_LongestContinuousSubarrayAbsDiff {
    public static int longestSubarray(int[] nums, int limit) {
        Deque<Integer> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
        int left = 0, ans = 0;
        for (int right = 0; right < nums.length; right++) {
            while (!maxD.isEmpty() && nums[maxD.peekLast()] <= nums[right]) maxD.pollLast();
            while (!minD.isEmpty() && nums[minD.peekLast()] >= nums[right]) minD.pollLast();
            maxD.offerLast(right); minD.offerLast(right);
            while (nums[maxD.peekFirst()] - nums[minD.peekFirst()] > limit) {
                left++;
                if (maxD.peekFirst() < left) maxD.pollFirst();
                if (minD.peekFirst() < left) minD.pollFirst();
            }
            ans = Math.max(ans, right - left + 1);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(longestSubarray(new int[]{8,2,4,7}, 4)); // 2
        System.out.println(longestSubarray(new int[]{10,1,2,4,7,2}, 5)); // 4
    }
}
