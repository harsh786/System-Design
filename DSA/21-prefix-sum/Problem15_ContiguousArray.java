/**
 * Problem 15: Contiguous Array (LeetCode 525)
 * 
 * Pattern: Replace 0 with -1, then find longest subarray with sum 0 using prefix sum + HashMap
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the longest period where request success/failure
 * rates are perfectly balanced (50/50) for A/B test validity.
 */
import java.util.*;

public class Problem15_ContiguousArray {

    public static int findMaxLength(int[] nums) {
        Map<Integer, Integer> firstSeen = new HashMap<>();
        firstSeen.put(0, -1);
        int sum = 0, maxLen = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i] == 0 ? -1 : 1;
            if (firstSeen.containsKey(sum))
                maxLen = Math.max(maxLen, i - firstSeen.get(sum));
            else
                firstSeen.put(sum, i);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        assert findMaxLength(new int[]{0, 1}) == 2;
        assert findMaxLength(new int[]{0, 1, 0}) == 2;
        assert findMaxLength(new int[]{0, 0, 1, 0, 0, 0, 1, 1}) == 6;
        assert findMaxLength(new int[]{0}) == 0;
        System.out.println("All tests passed!");
    }
}
