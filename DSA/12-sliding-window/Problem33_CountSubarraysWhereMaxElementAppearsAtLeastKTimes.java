/**
 * Problem 33: Count Subarrays Where Max Element Appears at Least K Times (LeetCode 2962)
 * 
 * Approach: Find global max. Sliding window counting occurrences of max.
 * When count >= k, all extensions to right are valid.
 * Window invariant: count of max element in window.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting intervals where peak load exceeded threshold
 * at least K times for capacity breach reporting.
 */
public class Problem33_CountSubarraysWhereMaxElementAppearsAtLeastKTimes {
    public static long countSubarrays(int[] nums, int k) {
        int max = 0;
        for (int n : nums) max = Math.max(max, n);
        long result = 0;
        int left = 0, count = 0;
        for (int right = 0; right < nums.length; right++) {
            if (nums[right] == max) count++;
            while (count >= k) {
                result += nums.length - right;
                if (nums[left] == max) count--;
                left++;
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(countSubarrays(new int[]{1,3,2,3,3}, 2)); // 6
        System.out.println(countSubarrays(new int[]{1,4,2,1}, 3));   // 0
    }
}
