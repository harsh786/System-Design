import java.util.*;
/**
 * Problem 21: Longest Continuous Subarray With Absolute Diff <= Limit (LeetCode 1438)
 * 
 * Approach: Sliding window with two monotonic deques (max-deque and min-deque).
 * Window invariant: max - min in window <= limit.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like finding the longest period where metric variance stays
 * within acceptable bounds (stable system detection).
 */
public class Problem21_LongestContinuousSubarrayWithAbsoluteDiff {
    public static int longestSubarray(int[] nums, int limit) {
        Deque<Integer> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
        int left = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            while (!maxD.isEmpty() && nums[maxD.peekLast()] <= nums[right]) maxD.pollLast();
            while (!minD.isEmpty() && nums[minD.peekLast()] >= nums[right]) minD.pollLast();
            maxD.offerLast(right);
            minD.offerLast(right);
            while (nums[maxD.peekFirst()] - nums[minD.peekFirst()] > limit) {
                left++;
                if (maxD.peekFirst() < left) maxD.pollFirst();
                if (minD.peekFirst() < left) minD.pollFirst();
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(longestSubarray(new int[]{8,2,4,7}, 4));        // 2
        System.out.println(longestSubarray(new int[]{10,1,2,4,7,2}, 5));   // 4
        System.out.println(longestSubarray(new int[]{4,2,2,2,4,4,2,2}, 0)); // 3
    }
}
