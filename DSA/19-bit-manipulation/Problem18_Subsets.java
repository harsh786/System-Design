/**
 * Problem 18: Subsets (Bitmask approach)
 * Generate all subsets of a set with distinct integers.
 * 
 * Approach: For n elements, iterate masks 0 to 2^n - 1. Each bit indicates inclusion.
 * Time: O(n * 2^n), Space: O(n * 2^n)
 * 
 * Production Analogy: Generating all possible feature flag combinations for A/B testing.
 */
import java.util.*;

public class Problem18_Subsets {
    public static List<List<Integer>> subsets(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        int n = nums.length;
        for (int mask = 0; mask < (1 << n); mask++) {
            List<Integer> subset = new ArrayList<>();
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) subset.add(nums[i]);
            }
            result.add(subset);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(subsets(new int[]{1,2,3}));
        System.out.println(subsets(new int[]{0}));
    }
}
