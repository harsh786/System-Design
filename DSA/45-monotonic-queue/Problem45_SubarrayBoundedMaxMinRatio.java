/**
 * Problem: Problem45 SubarrayBoundedMaxMinRatio - Longest subarray where max/min ratio <= threshold.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Longest subarray where max/min ratio <= threshold.
 */
import java.util.*;

public class Problem45_SubarrayBoundedMaxMinRatio {
    // Longest subarray where max / min <= threshold
    public static int longestBoundedRatio(int[] nums, double threshold) {
        Deque<Integer> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
        int left = 0, ans = 0;
        for (int right = 0; right < nums.length; right++) {
            while (!maxD.isEmpty() && nums[maxD.peekLast()] <= nums[right]) maxD.pollLast();
            while (!minD.isEmpty() && nums[minD.peekLast()] >= nums[right]) minD.pollLast();
            maxD.offerLast(right); minD.offerLast(right);
            while ((double) nums[maxD.peekFirst()] / nums[minD.peekFirst()] > threshold) {
                left++;
                if (maxD.peekFirst() < left) maxD.pollFirst();
                if (minD.peekFirst() < left) minD.pollFirst();
            }
            ans = Math.max(ans, right - left + 1);
        }
        return ans;
    }

    public static void main(String[] args) {
        System.out.println(longestBoundedRatio(new int[]{2, 4, 3, 6, 8, 1}, 2.0)); // 4
    }
}
