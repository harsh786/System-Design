/**
 * Problem 8: Maximum Size Subarray Sum Equals k (LeetCode 325)
 * 
 * Pattern: Prefix sum + HashMap storing first occurrence of each prefix sum
 * 
 * If prefix[j] - prefix[i] == k, length is j - i. Store earliest index for each prefix sum.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the longest continuous period where net resource
 * consumption equals exactly a quota value for capacity planning.
 */
import java.util.*;

public class Problem08_MaxSizeSubarraySumEqualsK {

    public static int maxSubArrayLen(int[] nums, int k) {
        Map<Integer, Integer> firstOccurrence = new HashMap<>();
        firstOccurrence.put(0, -1);
        int sum = 0, maxLen = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i];
            if (firstOccurrence.containsKey(sum - k))
                maxLen = Math.max(maxLen, i - firstOccurrence.get(sum - k));
            firstOccurrence.putIfAbsent(sum, i);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        assert maxSubArrayLen(new int[]{1, -1, 5, -2, 3}, 3) == 4;
        assert maxSubArrayLen(new int[]{-2, -1, 2, 1}, 1) == 2;
        assert maxSubArrayLen(new int[]{1, 0, -1}, -1) == 2;
        assert maxSubArrayLen(new int[]{1}, 1) == 1;
        System.out.println("All tests passed!");
    }
}
