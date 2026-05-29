import java.util.*;

/**
 * Problem 49: Power Set Generation (D&C)
 * 
 * D&C Approach:
 * - DIVIDE: Consider element at current index: include or exclude
 * - CONQUER: Recursively generate subsets for remaining elements
 * - COMBINE: Subsets WITH current element + subsets WITHOUT = all subsets
 * 
 * Alternative D&C: Split array in half, generate power sets of each half,
 * combine by taking cross-product.
 * 
 * Time: O(2^n * n), Space: O(2^n * n)
 * 
 * Production Analogy:
 * - Feature flag combinations testing (all combinations of enabled features)
 * - Exhaustive configuration testing
 * - Generating all possible filter combinations in search systems
 */
public class Problem49_PowerSetGeneration {

    // D&C: include/exclude approach
    public static List<List<Integer>> subsets(int[] nums) {
        List<List<Integer>> result = new ArrayList<>();
        generateDC(nums, 0, new ArrayList<>(), result);
        return result;
    }

    private static void generateDC(int[] nums, int idx, List<Integer> current, List<List<Integer>> result) {
        if (idx == nums.length) {
            result.add(new ArrayList<>(current));
            return;
        }
        // Exclude current element
        generateDC(nums, idx + 1, current, result);
        // Include current element
        current.add(nums[idx]);
        generateDC(nums, idx + 1, current, result);
        current.remove(current.size() - 1);
    }

    // True D&C: split in half, combine cross-product
    public static List<List<Integer>> subsetsDC(int[] nums) {
        return divideAndConquer(nums, 0, nums.length - 1);
    }

    private static List<List<Integer>> divideAndConquer(int[] nums, int lo, int hi) {
        List<List<Integer>> result = new ArrayList<>();
        if (lo > hi) {
            result.add(new ArrayList<>());
            return result;
        }
        if (lo == hi) {
            result.add(new ArrayList<>());
            result.add(new ArrayList<>(Arrays.asList(nums[lo])));
            return result;
        }
        int mid = lo + (hi - lo) / 2;
        List<List<Integer>> left = divideAndConquer(nums, lo, mid);
        List<List<Integer>> right = divideAndConquer(nums, mid + 1, hi);
        
        // Cross-product
        for (List<Integer> l : left) {
            for (List<Integer> r : right) {
                List<Integer> combined = new ArrayList<>(l);
                combined.addAll(r);
                result.add(combined);
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(subsets(new int[]{1, 2, 3}));
        System.out.println("Size: " + subsets(new int[]{1, 2, 3}).size()); // 8
        System.out.println(subsetsDC(new int[]{1, 2, 3}));
        System.out.println(subsets(new int[]{})); // [[]]
        System.out.println(subsets(new int[]{0})); // [[], [0]]
    }
}
