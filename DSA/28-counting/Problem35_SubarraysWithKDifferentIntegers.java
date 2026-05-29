/**
 * Problem: Subarrays with K Different Integers (LeetCode 992)
 * Approach: atMost(k) - atMost(k-1) using sliding window with counting
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Cardinality-bounded window analysis in stream processing
 */
import java.util.*;
public class Problem35_SubarraysWithKDifferentIntegers {
    public int subarraysWithKDistinct(int[] nums, int k) {
        return atMost(nums, k) - atMost(nums, k-1);
    }
    int atMost(int[] nums, int k) {
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
        System.out.println(new Problem35_SubarraysWithKDifferentIntegers()
            .subarraysWithKDistinct(new int[]{1,2,1,2,3}, 2)); // 7
    }
}
