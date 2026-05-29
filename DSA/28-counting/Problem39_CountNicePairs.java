/**
 * Problem: Count Nice Pairs in an Array (LeetCode 1814)
 * Approach: nums[i] - rev(nums[i]) == nums[j] - rev(nums[j]) -> count same diff
 * Complexity: O(n) time, O(n) space
 * Production Analogy: Equivalence class counting in data normalization
 */
import java.util.*;
public class Problem39_CountNicePairs {
    public int countNicePairs(int[] nums) {
        int MOD = 1_000_000_007;
        Map<Integer, Integer> map = new HashMap<>();
        long count = 0;
        for (int n : nums) {
            int diff = n - rev(n);
            count += map.getOrDefault(diff, 0);
            map.merge(diff, 1, Integer::sum);
        }
        return (int)(count % MOD);
    }
    int rev(int n) { int r = 0; while (n > 0) { r = r*10 + n%10; n /= 10; } return r; }
    public static void main(String[] args) {
        System.out.println(new Problem39_CountNicePairs().countNicePairs(new int[]{42,11,1,97})); // 2
    }
}
