/**
 * Problem 11: Get Equal Substrings Within Budget (LeetCode 1208)
 * 
 * Approach: Sliding window where cost = sum of |s[i]-t[i]| in window <= maxCost.
 * Window invariant: total transformation cost in window <= maxCost.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest sequence of API transformations
 * you can perform within a compute budget.
 */
public class Problem11_GetEqualSubstringsWithinBudget {
    public static int equalSubstring(String s, String t, int maxCost) {
        int left = 0, cost = 0, maxLen = 0;
        for (int right = 0; right < s.length(); right++) {
            cost += Math.abs(s.charAt(right) - t.charAt(right));
            while (cost > maxCost) {
                cost -= Math.abs(s.charAt(left) - t.charAt(left));
                left++;
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(equalSubstring("abcd", "bcdf", 3));   // 3
        System.out.println(equalSubstring("abcd", "cdef", 3));   // 1
        System.out.println(equalSubstring("abcd", "acde", 0));   // 1
    }
}
