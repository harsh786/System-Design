/**
 * Problem 4: Continuous Subarray Sum (LeetCode 523)
 * 
 * Pattern: Prefix sum mod k + HashMap storing first occurrence index
 * 
 * If prefix[j] % k == prefix[i] % k and j - i >= 2, subarray (i,j] sums to multiple of k.
 * 
 * Time: O(n), Space: O(min(n, k))
 * 
 * Production Analogy: Billing cycle alignment—finding periods where cumulative
 * charges are exact multiples of a billing unit (e.g., $100 increments).
 */
import java.util.*;

public class Problem04_ContinuousSubarraySum {

    public static boolean checkSubarraySum(int[] nums, int k) {
        Map<Integer, Integer> modIndex = new HashMap<>();
        modIndex.put(0, -1);
        int sum = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i];
            int mod = sum % k;
            if (mod < 0) mod += k; // handle negative
            if (modIndex.containsKey(mod)) {
                if (i - modIndex.get(mod) >= 2) return true;
            } else {
                modIndex.put(mod, i);
            }
        }
        return false;
    }

    public static void main(String[] args) {
        assert checkSubarraySum(new int[]{23, 2, 4, 6, 7}, 6) == true;
        assert checkSubarraySum(new int[]{23, 2, 6, 4, 7}, 6) == true;
        assert checkSubarraySum(new int[]{23, 2, 6, 4, 7}, 13) == false;
        assert checkSubarraySum(new int[]{0, 0}, 1) == true;
        assert checkSubarraySum(new int[]{1, 0}, 2) == false;
        System.out.println("All tests passed!");
    }
}
