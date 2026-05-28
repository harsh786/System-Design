import java.util.*;
/**
 * Problem 43: Distinct Numbers in Each Subarray (Count distinct in each window of size k)
 * 
 * Approach: Fixed window of size k with frequency map.
 * Window invariant: track frequency of each element, map.size() = distinct count.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Like tracking unique IP addresses per fixed time bucket
 * for cardinality estimation in network monitoring.
 */
public class Problem43_DistinctNumbersInEachSubarray {
    public static int[] distinctNumbers(int[] nums, int k) {
        Map<Integer, Integer> freq = new HashMap<>();
        int[] result = new int[nums.length - k + 1];
        for (int i = 0; i < nums.length; i++) {
            freq.merge(nums[i], 1, Integer::sum);
            if (i >= k) {
                freq.merge(nums[i - k], -1, Integer::sum);
                if (freq.get(nums[i - k]) == 0) freq.remove(nums[i - k]);
            }
            if (i >= k - 1) result[i - k + 1] = freq.size();
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(distinctNumbers(new int[]{1,2,3,2,2,1,3}, 3))); // [3,2,2,2,3]
        System.out.println(Arrays.toString(distinctNumbers(new int[]{1,1,1,1}, 2))); // [1,1,1]
        System.out.println(Arrays.toString(distinctNumbers(new int[]{1,2,3,4}, 2))); // [2,2,2]
    }
}
