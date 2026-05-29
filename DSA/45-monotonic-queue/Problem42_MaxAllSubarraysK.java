/**
 * Problem: Problem42 MaxAllSubarraysK - Return max of all subarrays of fixed size k.
 * Approach: Monotonic deque maintaining order invariant over sliding window.
 * Time: O(n) | Space: O(k) or O(n)
 * Production Analogy: Return max of all subarrays of fixed size k.
 */
import java.util.*;

public class Problem42_MaxAllSubarraysK {
    public static int[] maxOfSubarrays(int[] nums, int k) {
        int n = nums.length;
        int[] result = new int[n - k + 1];
        Deque<Integer> deque = new ArrayDeque<>();
        for (int i = 0; i < n; i++) {
            while (!deque.isEmpty() && deque.peekFirst() <= i - k) deque.pollFirst();
            while (!deque.isEmpty() && nums[deque.peekLast()] <= nums[i]) deque.pollLast();
            deque.offerLast(i);
            if (i >= k - 1) result[i - k + 1] = nums[deque.peekFirst()];
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(maxOfSubarrays(new int[]{1, 3, -1, -3, 5, 3, 6, 7}, 3)));
    }
}
