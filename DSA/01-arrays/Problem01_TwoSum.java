import java.util.*;

/**
 * Problem 1: Two Sum
 * Given an array of integers and a target, return indices of two numbers that add up to target.
 * 
 * Production Analogy: Like a cache lookup - given a request ID, find its complementary 
 * service response from a hashmap of pending requests.
 * 
 * Brute Force: O(n^2) time, O(1) space - check every pair
 * Optimal: O(n) time, O(n) space - hash map for complement lookup
 */
public class Problem01_TwoSum {

    // Brute Force: O(n^2)
    public static int[] twoSumBrute(int[] nums, int target) {
        for (int i = 0; i < nums.length; i++)
            for (int j = i + 1; j < nums.length; j++)
                if (nums[i] + nums[j] == target) return new int[]{i, j};
        return new int[]{};
    }

    // Optimal: O(n) time, O(n) space
    public static int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (map.containsKey(complement)) return new int[]{map.get(complement), i};
            map.put(nums[i], i);
        }
        return new int[]{};
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(twoSum(new int[]{2,7,11,15}, 9))); // [0,1]
        System.out.println(Arrays.toString(twoSum(new int[]{3,2,4}, 6)));     // [1,2]
        System.out.println(Arrays.toString(twoSum(new int[]{3,3}, 6)));       // [0,1]
        System.out.println(Arrays.toString(twoSumBrute(new int[]{2,7,11,15}, 9))); // [0,1]
    }
}
