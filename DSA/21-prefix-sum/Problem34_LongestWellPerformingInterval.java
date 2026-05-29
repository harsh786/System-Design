/**
 * Problem 34: Longest Well-Performing Interval (LeetCode 1124)
 * 
 * Pattern: Transform hours > 8 to +1, else -1. Find longest subarray with sum > 0.
 * Use prefix sum + HashMap storing first occurrence of each prefix value.
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Finding the longest period where a service was "healthy"
 * (more good minutes than bad minutes).
 */
import java.util.*;

public class Problem34_LongestWellPerformingInterval {

    public static int longestWPI(int[] hours) {
        Map<Integer, Integer> firstOccurrence = new HashMap<>();
        int sum = 0, maxLen = 0;
        for (int i = 0; i < hours.length; i++) {
            sum += hours[i] > 8 ? 1 : -1;
            if (sum > 0) {
                maxLen = i + 1;
            } else {
                firstOccurrence.putIfAbsent(sum, i);
                if (firstOccurrence.containsKey(sum - 1))
                    maxLen = Math.max(maxLen, i - firstOccurrence.get(sum - 1));
            }
        }
        return maxLen;
    }

    public static void main(String[] args) {
        assert longestWPI(new int[]{9, 9, 6, 0, 6, 6, 9}) == 3;
        assert longestWPI(new int[]{6, 6, 6}) == 0;
        assert longestWPI(new int[]{9, 6, 9}) == 3;
        System.out.println("All tests passed!");
    }
}
