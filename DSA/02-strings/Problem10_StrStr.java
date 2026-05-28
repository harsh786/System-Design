import java.util.*;

/**
 * Problem 10: Find the Index of the First Occurrence in a String (LeetCode 28)
 * 
 * Approach 1 (Brute): Slide needle over haystack. O(n*m) time.
 * Approach 2 (Optimal): KMP algorithm. O(n+m) time, O(m) space.
 * 
 * Production Analogy: Like searching for a pattern in log files - KMP avoids
 * re-scanning already matched portions (similar to how grep optimizes searches).
 */
public class Problem10_StrStr {

    // Brute force
    public static int strStrBrute(String haystack, String needle) {
        if (needle.isEmpty()) return 0;
        for (int i = 0; i <= haystack.length() - needle.length(); i++) {
            if (haystack.substring(i, i + needle.length()).equals(needle)) return i;
        }
        return -1;
    }

    // KMP
    public static int strStr(String haystack, String needle) {
        if (needle.isEmpty()) return 0;
        int[] lps = buildLPS(needle);
        int i = 0, j = 0;
        while (i < haystack.length()) {
            if (haystack.charAt(i) == needle.charAt(j)) { i++; j++; }
            if (j == needle.length()) return i - j;
            else if (i < haystack.length() && haystack.charAt(i) != needle.charAt(j)) {
                if (j != 0) j = lps[j - 1];
                else i++;
            }
        }
        return -1;
    }

    private static int[] buildLPS(String pattern) {
        int[] lps = new int[pattern.length()];
        int len = 0, i = 1;
        while (i < pattern.length()) {
            if (pattern.charAt(i) == pattern.charAt(len)) { lps[i++] = ++len; }
            else if (len != 0) { len = lps[len - 1]; }
            else { lps[i++] = 0; }
        }
        return lps;
    }

    public static void main(String[] args) {
        System.out.println(strStr("sadbutsad", "sad")); // 0
        System.out.println(strStr("leetcode", "leeto")); // -1
        System.out.println(strStr("hello", "ll"));       // 2
        System.out.println(strStr("a", "a"));            // 0
    }
}
