import java.util.*;
/**
 * Problem 5: Minimum Window Substring (LeetCode 76)
 * 
 * Approach: Expand right to include all chars of t, then shrink left to minimize.
 * Window invariant: window contains all characters of t with required frequencies.
 * 
 * Time: O(n + m), Space: O(charset)
 * 
 * Production Analogy: Like finding the shortest time window in logs that contains
 * all required error types for root cause analysis.
 */
public class Problem05_MinimumWindowSubstring {
    public static String minWindow(String s, String t) {
        if (s.length() < t.length()) return "";
        Map<Character, Integer> need = new HashMap<>();
        for (char c : t.toCharArray()) need.merge(c, 1, Integer::sum);
        int left = 0, matched = 0, minLen = Integer.MAX_VALUE, minStart = 0;
        Map<Character, Integer> window = new HashMap<>();
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            window.merge(c, 1, Integer::sum);
            if (need.containsKey(c) && window.get(c).intValue() == need.get(c).intValue()) {
                matched++;
            }
            while (matched == need.size()) {
                if (right - left + 1 < minLen) {
                    minLen = right - left + 1;
                    minStart = left;
                }
                char lc = s.charAt(left);
                if (need.containsKey(lc) && window.get(lc).intValue() == need.get(lc).intValue()) {
                    matched--;
                }
                window.merge(lc, -1, Integer::sum);
                left++;
            }
        }
        return minLen == Integer.MAX_VALUE ? "" : s.substring(minStart, minStart + minLen);
    }

    public static void main(String[] args) {
        System.out.println(minWindow("ADOBECODEBANC", "ABC")); // "BANC"
        System.out.println(minWindow("a", "a"));                // "a"
        System.out.println(minWindow("a", "aa"));               // ""
        System.out.println(minWindow("aa", "aa"));              // "aa"
        System.out.println(minWindow("cabwefgewcwaefgcf", "cae")); // "cwae"
    }
}
