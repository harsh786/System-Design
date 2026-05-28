import java.util.*;
/**
 * Problem 48: Count Complete Subarrays in an Array (LeetCode 2799)
 * 
 * Approach: A subarray is complete if it contains all distinct elements of the array.
 * Sliding window: when window has all distinct, count += (n - right).
 * Window invariant: track distinct count in window vs total distinct.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like counting time windows where all microservices have
 * reported at least once (full system heartbeat).
 */
public class Problem48_CountCompleteSubarraysInAnArray {
    public static int countCompleteSubarrays(int[] nums) {
        Set<Integer> all = new HashSet<>();
        for (int n : nums) all.add(n);
        int totalDistinct = all.size();
        Map<Integer, Integer> freq = new HashMap<>();
        int left = 0, count = 0;
        for (int right = 0; right < nums.length; right++) {
            freq.merge(nums[right], 1, Integer::sum);
            while (freq.size() == totalDistinct) {
                count += nums.length - right;
                freq.merge(nums[left], -1, Integer::sum);
                if (freq.get(nums[left]) == 0) freq.remove(nums[left]);
                left++;
            }
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(countCompleteSubarrays(new int[]{1,3,1,2,2})); // 4
        System.out.println(countCompleteSubarrays(new int[]{5,5,5,5}));   // 10
    }
}
