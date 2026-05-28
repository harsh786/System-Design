import java.util.*;

/**
 * Problem 29: Repeated Substring Pattern (LeetCode 459)
 * 
 * Approach: If s is made of repeated pattern, then (s+s)[1:-1] contains s.
 * O(n) time with KMP, O(n) space.
 * 
 * Production Analogy: Like detecting periodic patterns in time-series data (e.g.,
 * recurring load spikes every N minutes).
 */
public class Problem29_RepeatedSubstringPattern {

    public static boolean repeatedSubstringPattern(String s) {
        String doubled = (s + s).substring(1, 2 * s.length() - 1);
        return doubled.contains(s);
    }

    public static void main(String[] args) {
        System.out.println(repeatedSubstringPattern("abab"));   // true
        System.out.println(repeatedSubstringPattern("aba"));    // false
        System.out.println(repeatedSubstringPattern("abcabcabc")); // true
    }
}
