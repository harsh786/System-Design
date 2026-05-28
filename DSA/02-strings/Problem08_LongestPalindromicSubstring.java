import java.util.*;

/**
 * Problem 8: Longest Palindromic Substring (LeetCode 5)
 * 
 * Approach 1 (Brute): Check all substrings. O(n^3).
 * Approach 2 (Optimal): Expand around center. O(n^2) time, O(1) space.
 * 
 * Production Analogy: Like finding the longest symmetric pattern in time-series data
 * by checking each point as a potential center of symmetry.
 */
public class Problem08_LongestPalindromicSubstring {

    public static String longestPalindrome(String s) {
        if (s.length() < 2) return s;
        int start = 0, maxLen = 1;
        for (int i = 0; i < s.length(); i++) {
            int len1 = expand(s, i, i);
            int len2 = expand(s, i, i + 1);
            int len = Math.max(len1, len2);
            if (len > maxLen) {
                maxLen = len;
                start = i - (len - 1) / 2;
            }
        }
        return s.substring(start, start + maxLen);
    }

    private static int expand(String s, int l, int r) {
        while (l >= 0 && r < s.length() && s.charAt(l) == s.charAt(r)) { l--; r++; }
        return r - l - 1;
    }

    public static void main(String[] args) {
        System.out.println(longestPalindrome("babad")); // "bab" or "aba"
        System.out.println(longestPalindrome("cbbd"));  // "bb"
        System.out.println(longestPalindrome("a"));     // "a"
        System.out.println(longestPalindrome("ac"));    // "a"
    }
}
