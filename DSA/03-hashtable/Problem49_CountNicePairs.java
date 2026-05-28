import java.util.*;

/**
 * Problem 49: Count Nice Pairs in an Array
 * Count pairs where nums[i] + rev(nums[j]) == nums[j] + rev(nums[i]).
 * Rearranged: (nums[i] - rev(nums[i])) == (nums[j] - rev(nums[j]))
 *
 * Approach: Compute diff = num - rev(num) for each element. Count pairs with same diff.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Like identifying equivalent transformation groups in data pipelines -
 * items that behave identically under a specific transformation can be batched together.
 */
public class Problem49_CountNicePairs {
    private static final int MOD = 1_000_000_007;

    public int countNicePairs(int[] nums) {
        Map<Integer, Integer> freq = new HashMap<>();
        long count = 0;
        for (int n : nums) {
            int diff = n - rev(n);
            count = (count + freq.getOrDefault(diff, 0)) % MOD;
            freq.merge(diff, 1, Integer::sum);
        }
        return (int) count;
    }

    private int rev(int n) {
        int r = 0;
        while (n > 0) { r = r * 10 + n % 10; n /= 10; }
        return r;
    }

    public static void main(String[] args) {
        Problem49_CountNicePairs sol = new Problem49_CountNicePairs();
        System.out.println(sol.countNicePairs(new int[]{42,11,1,97})); // 2
        System.out.println(sol.countNicePairs(new int[]{13,10,35,24,76})); // 4
    }
}
