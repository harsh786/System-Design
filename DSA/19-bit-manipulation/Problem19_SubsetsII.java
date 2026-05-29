/**
 * Problem 19: Subsets II (Bitmask with duplicates)
 * Generate all unique subsets from array with possible duplicates.
 * 
 * Approach: Sort, use bitmask, skip duplicate subsets via set or sorted comparison.
 * Time: O(n * 2^n), Space: O(n * 2^n)
 * 
 * Production Analogy: Generating unique permission sets from overlapping role definitions.
 */
import java.util.*;

public class Problem19_SubsetsII {
    public static List<List<Integer>> subsetsWithDup(int[] nums) {
        Arrays.sort(nums);
        Set<List<Integer>> resultSet = new HashSet<>();
        int n = nums.length;
        for (int mask = 0; mask < (1 << n); mask++) {
            List<Integer> subset = new ArrayList<>();
            for (int i = 0; i < n; i++) {
                if ((mask & (1 << i)) != 0) subset.add(nums[i]);
            }
            resultSet.add(subset);
        }
        return new ArrayList<>(resultSet);
    }

    public static void main(String[] args) {
        System.out.println(subsetsWithDup(new int[]{1,2,2}));
        System.out.println(subsetsWithDup(new int[]{0}));
    }
}
