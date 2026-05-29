/**
 * Problem: Continuous Subarrays (LC 2762)
 * Two deques (max/min) + sliding window counting valid subarrays.
 * Time: O(n) | Space: O(n)
 * Production Analogy: Count valid time intervals where system metrics stay within bounds.
 */
import java.util.*;

public class Problem18_ContinuousSubarrays {
    public static long continuousSubarrays(int[] nums) {
        int n = nums.length, left = 0;
        long count = 0;
        Deque<Integer> maxD = new ArrayDeque<>(), minD = new ArrayDeque<>();
        for (int right = 0; right < n; right++) {
            while (!maxD.isEmpty() && nums[maxD.peekLast()] <= nums[right]) maxD.pollLast();
            while (!minD.isEmpty() && nums[minD.peekLast()] >= nums[right]) minD.pollLast();
            maxD.offerLast(right); minD.offerLast(right);
            while (nums[maxD.peekFirst()] - nums[minD.peekFirst()] > 2) {
                left++;
                if (maxD.peekFirst() < left) maxD.pollFirst();
                if (minD.peekFirst() < left) minD.pollFirst();
            }
            count += right - left + 1;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(continuousSubarrays(new int[]{5,4,2,4})); // 8
    }
}
