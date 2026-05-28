import java.util.*;
/**
 * Problem 9: Subarrays with K Different Integers (LeetCode 992)
 * 
 * Approach: exactly(k) = atMost(k) - atMost(k-1)
 * Window invariant: count of distinct integers in window <= k.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Like counting time windows where exactly K unique users
 * are active - useful for capacity planning.
 */
public class Problem09_SubarraysWithKDifferentIntegers {
    public static int subarraysWithKDistinct(int[] nums, int k) {
        return atMost(nums, k) - atMost(nums, k - 1);
    }

    private static int atMost(int[] nums, int k) {
        Map<Integer, Integer> count = new HashMap<>();
        int left = 0, result = 0;
        for (int right = 0; right < nums.length; right++) {
            count.merge(nums[right], 1, Integer::sum);
            while (count.size() > k) {
                count.merge(nums[left], -1, Integer::sum);
                if (count.get(nums[left]) == 0) count.remove(nums[left]);
                left++;
            }
            result += right - left + 1;
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(subarraysWithKDistinct(new int[]{1,2,1,2,3}, 2)); // 7
        System.out.println(subarraysWithKDistinct(new int[]{1,2,1,3,4}, 3)); // 3
        System.out.println(subarraysWithKDistinct(new int[]{1,1,1,1}, 1));   // 10
    }
}
