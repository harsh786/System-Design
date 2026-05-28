import java.util.*;

/**
 * Problem 46: Shortest Palindrome (LeetCode 214)
 * 
 * Find shortest palindrome by adding chars in front of s.
 * Approach: Find longest palindrome prefix using KMP on s + "#" + reverse(s).
 * O(n) time, O(n) space.
 * 
 * Production Analogy: Like finding the minimum prefix to add to make a URL path
 * symmetric for routing purposes.
 */
public class Problem46_ShortestPalindrome {

    public static String shortestPalindrome(String s) {
        String rev = new StringBuilder(s).reverse().toString();
        String combined = s + "#" + rev;
        int[] lps = buildLPS(combined);
        int palLen = lps[combined.length() - 1];
        return rev.substring(0, s.length() - palLen) + s;
    }

    private static int[] buildLPS(String s) {
        int[] lps = new int[s.length()];
        int len = 0, i = 1;
        while (i < s.length()) {
            if (s.charAt(i) == s.charAt(len)) lps[i++] = ++len;
            else if (len != 0) len = lps[len - 1];
            else lps[i++] = 0;
        }
        return lps;
    }

    public static void main(String[] args) {
        System.out.println(shortestPalindrome("aacecaaa")); // "aaacecaaa"
        System.out.println(shortestPalindrome("abcd"));     // "dcbabcd"
        System.out.println(shortestPalindrome(""));         // ""
    }
}
