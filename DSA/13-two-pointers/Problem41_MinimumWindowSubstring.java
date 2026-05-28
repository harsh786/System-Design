/**
 * Problem 41: Minimum Window Substring
 * 
 * Find minimum window in s that contains all characters of t.
 * 
 * Approach: Sliding window with frequency count. Expand right to cover t,
 * shrink left to minimize window.
 * Time: O(m+n), Space: O(charset)
 * 
 * Production Analogy: Like finding the smallest log time window that contains
 * all required audit events for compliance verification.
 */
import java.util.HashMap;

public class Problem41_MinimumWindowSubstring {
    public static String minWindow(String s, String t) {
        if (s.length() < t.length()) return "";
        HashMap<Character, Integer> need = new HashMap<>(), have = new HashMap<>();
        for (char c : t.toCharArray()) need.merge(c, 1, Integer::sum);
        int required = need.size(), formed = 0;
        int left = 0, minLen = Integer.MAX_VALUE, minStart = 0;
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            have.merge(c, 1, Integer::sum);
            if (need.containsKey(c) && have.get(c).intValue() == need.get(c).intValue()) formed++;
            while (formed == required) {
                if (right - left + 1 < minLen) { minLen = right - left + 1; minStart = left; }
                char lc = s.charAt(left);
                have.merge(lc, -1, Integer::sum);
                if (need.containsKey(lc) && have.get(lc) < need.get(lc)) formed--;
                left++;
            }
        }
        return minLen == Integer.MAX_VALUE ? "" : s.substring(minStart, minStart + minLen);
    }

    public static void main(String[] args) {
        System.out.println(minWindow("ADOBECODEBANC", "ABC")); // BANC
        System.out.println(minWindow("a", "a")); // a
        System.out.println(minWindow("a", "aa")); // ""
    }
}
