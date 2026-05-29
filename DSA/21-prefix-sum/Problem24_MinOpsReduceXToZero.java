/**
 * Problem 24: Minimum Operations to Reduce X to Zero (LeetCode 1658)
 * 
 * Pattern: Find longest subarray with sum = totalSum - x (prefix sum + HashMap)
 * Removing from edges = keeping middle. Longest middle = fewest operations.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding minimum number of head/tail log entries to trim
 * to reach a target cumulative size for log rotation.
 */
import java.util.*;

public class Problem24_MinOpsReduceXToZero {

    public static int minOperations(int[] nums, int x) {
        int total = 0;
        for (int n : nums) total += n;
        int target = total - x;
        if (target < 0) return -1;
        if (target == 0) return nums.length;

        Map<Integer, Integer> map = new HashMap<>();
        map.put(0, -1);
        int sum = 0, maxLen = -1;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i];
            if (map.containsKey(sum - target))
                maxLen = Math.max(maxLen, i - map.get(sum - target));
            map.putIfAbsent(sum, i);
        }
        return maxLen == -1 ? -1 : nums.length - maxLen;
    }

    public static void main(String[] args) {
        assert minOperations(new int[]{1, 1, 4, 2, 3}, 5) == 2;
        assert minOperations(new int[]{5, 6, 7, 8, 9}, 4) == -1;
        assert minOperations(new int[]{3, 2, 20, 1, 1, 3}, 10) == 5;
        System.out.println("All tests passed!");
    }
}
