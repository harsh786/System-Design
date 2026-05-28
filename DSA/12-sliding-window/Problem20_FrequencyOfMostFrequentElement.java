import java.util.*;
/**
 * Problem 20: Frequency of the Most Frequent Element (LeetCode 1838)
 * 
 * Approach: Sort, then sliding window. Cost to make all elements == nums[right]
 * is nums[right]*(windowSize) - windowSum <= k.
 * Window invariant: cost to equalize window <= k.
 * 
 * Time: O(n log n), Space: O(1)
 * 
 * Production Analogy: Like determining how many servers can be scaled to the same
 * capacity level within a given budget.
 */
public class Problem20_FrequencyOfMostFrequentElement {
    public static int maxFrequency(int[] nums, int k) {
        Arrays.sort(nums);
        long sum = 0;
        int left = 0, maxLen = 0;
        for (int right = 0; right < nums.length; right++) {
            sum += nums[right];
            // Cost = nums[right] * windowSize - sum
            while ((long) nums[right] * (right - left + 1) - sum > k) {
                sum -= nums[left++];
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(maxFrequency(new int[]{1,2,4}, 5));    // 3
        System.out.println(maxFrequency(new int[]{1,4,8,13}, 5)); // 2
        System.out.println(maxFrequency(new int[]{3,9,6}, 2));    // 1
    }
}
