/**
 * Problem 23: Minimum Window Subsequence (LeetCode 727)
 * 
 * Approach: Two-pointer. Find subsequence t in s going forward, then shrink backward.
 * Window invariant: window contains t as a subsequence.
 * 
 * Time: O(n * m), Space: O(1)
 * 
 * Production Analogy: Like finding the shortest log sequence that contains
 * a specific ordered pattern of events for debugging.
 */
public class Problem23_MinimumWindowSubsequence {
    public static String minWindow(String s, String t) {
        int minLen = Integer.MAX_VALUE, minStart = -1;
        int i = 0;
        while (i < s.length()) {
            // Forward: find all chars of t in order
            int j = 0;
            int start = i;
            while (start < s.length() && j < t.length()) {
                if (s.charAt(start) == t.charAt(j)) j++;
                start++;
            }
            if (j < t.length()) break;
            // start is one past end of window
            int end = start - 1;
            // Backward: shrink from end
            j = t.length() - 1;
            while (j >= 0) {
                if (s.charAt(end) == t.charAt(j)) j--;
                end--;
            }
            end++;
            if (start - end < minLen) {
                minLen = start - end;
                minStart = end;
            }
            i = end + 1;
        }
        return minStart == -1 ? "" : s.substring(minStart, minStart + minLen);
    }

    public static void main(String[] args) {
        System.out.println(minWindow("abcdebdde", "bde")); // "bcde"
        System.out.println(minWindow("jmeqksfrsdcmsiwvaovztaqenrat", "u")); // ""
        System.out.println(minWindow("abcde", "ace")); // "abcde"
    }
}
