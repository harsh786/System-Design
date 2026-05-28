import java.util.*;

/**
 * Problem 45: Minimum Window Subsequence (LeetCode 727)
 * 
 * Find shortest substring of s1 that contains s2 as a subsequence.
 * Approach: Two-pointer forward/backward scan. O(m*n) time, O(1) space.
 * 
 * Production Analogy: Like finding the shortest log window that contains a specific
 * sequence of events in order.
 */
public class Problem45_MinimumWindowSubsequence {

    public static String minWindow(String s, String t) {
        int m = s.length(), n = t.length();
        int start = -1, minLen = Integer.MAX_VALUE;
        int i = 0;
        while (i < m) {
            // Forward: find a window containing t as subsequence
            int j = 0;
            int begin = i;
            while (begin < m && j < n) {
                if (s.charAt(begin) == t.charAt(j)) j++;
                begin++;
            }
            if (j < n) break;
            // begin is one past end of window, backward to minimize
            int end = begin - 1;
            j = n - 1;
            while (j >= 0) {
                if (s.charAt(end) == t.charAt(j)) j--;
                end--;
            }
            end++;
            if (begin - end < minLen) {
                minLen = begin - end;
                start = end;
            }
            i = end + 1;
        }
        return start == -1 ? "" : s.substring(start, start + minLen);
    }

    public static void main(String[] args) {
        System.out.println(minWindow("abcdebdde", "bde")); // "bcde"
        System.out.println(minWindow("jmeqksfrsdcmsiwvaovztaqenrat", "u")); // ""
        System.out.println(minWindow("abcde", "ace")); // "abcde"
    }
}
