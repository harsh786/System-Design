import java.util.*;

/**
 * Problem 1: Two Sum
 * Given an array of integers and a target, return indices of two numbers that add up to target.
 *
 * Approach: Use HashMap to store complement (target - num) -> index.
 * For each element, check if it exists as a key in the map.
 *
 * Time Complexity: O(n) - single pass
 * Space Complexity: O(n) - HashMap storage
 *
 * Production Analogy: Like a matchmaking service - for each request, check if a compatible
 * partner already registered. Similar to order matching in trading systems.
 */
public class Problem01_TwoSum {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (map.containsKey(complement)) {
                return new int[]{map.get(complement), i};
            }
            map.put(nums[i], i);
        }
        return new int[]{};
    }

    public static void main(String[] args) {
        Problem01_TwoSum sol = new Problem01_TwoSum();
        // Test 1: Basic case
        System.out.println(Arrays.toString(sol.twoSum(new int[]{2,7,11,15}, 9))); // [0,1]
        // Test 2: Numbers not adjacent
        System.out.println(Arrays.toString(sol.twoSum(new int[]{3,2,4}, 6))); // [1,2]
        // Test 3: Same element used twice (different indices)
        System.out.println(Arrays.toString(sol.twoSum(new int[]{3,3}, 6))); // [0,1]
        // Test 4: Negative numbers
        System.out.println(Arrays.toString(sol.twoSum(new int[]{-1,-2,-3,-4,-5}, -8))); // [2,4]
    }
}
