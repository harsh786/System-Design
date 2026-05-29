/**
 * Problem 44: Zero Sum Subarray
 * 
 * Pattern: Prefix sum + HashSet. If prefix sum repeats, subarray between them sums to 0.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Detecting net-zero resource allocation loops in a transaction
 * ledger (money laundering detection pattern).
 */
import java.util.*;

public class Problem44_ZeroSumSubarray {

    public static boolean hasZeroSumSubarray(int[] nums) {
        Set<Integer> seen = new HashSet<>();
        seen.add(0);
        int sum = 0;
        for (int num : nums) {
            sum += num;
            if (seen.contains(sum)) return true;
            seen.add(sum);
        }
        return false;
    }

    // Return the actual subarray indices [start, end]
    public static int[] findZeroSumSubarray(int[] nums) {
        Map<Integer, Integer> firstIndex = new HashMap<>();
        firstIndex.put(0, -1);
        int sum = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i];
            if (firstIndex.containsKey(sum))
                return new int[]{firstIndex.get(sum) + 1, i};
            firstIndex.put(sum, i);
        }
        return new int[]{-1, -1};
    }

    public static void main(String[] args) {
        assert hasZeroSumSubarray(new int[]{4, 2, -3, 1, 6}) == true;
        assert hasZeroSumSubarray(new int[]{4, 2, 0, 1, 6}) == true;
        assert hasZeroSumSubarray(new int[]{1, 2, 3}) == false;
        assert Arrays.equals(findZeroSumSubarray(new int[]{1, 2, -3, 4}), new int[]{0, 2});
        System.out.println("All tests passed!");
    }
}
