import java.util.*;
/**
 * Problem 30: Maximum Erasure Value (LeetCode 1695)
 * 
 * Approach: Sliding window with unique elements, maximize sum.
 * Window invariant: all elements in window are unique.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like finding the highest-value batch of unique items
 * to process in a deduplication pipeline.
 */
public class Problem30_MaximumErasureValue {
    public static int maximumUniqueSubarray(int[] nums) {
        Set<Integer> set = new HashSet<>();
        int left = 0, sum = 0, maxSum = 0;
        for (int right = 0; right < nums.length; right++) {
            while (set.contains(nums[right])) {
                set.remove(nums[left]);
                sum -= nums[left++];
            }
            set.add(nums[right]);
            sum += nums[right];
            maxSum = Math.max(maxSum, sum);
        }
        return maxSum;
    }

    public static void main(String[] args) {
        System.out.println(maximumUniqueSubarray(new int[]{4,2,4,5,6}));  // 17
        System.out.println(maximumUniqueSubarray(new int[]{5,2,1,2,5,2,1,2,5})); // 8
    }
}
