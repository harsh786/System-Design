import java.util.*;

/**
 * Problem 12: Minimum Window Substring
 * Given strings s and t, return the minimum window in s that contains all characters of t.
 *
 * Approach: Sliding window with two frequency maps. Expand right to include all chars,
 * then shrink left to minimize window.
 *
 * Time Complexity: O(|s| + |t|)
 * Space Complexity: O(|s| + |t|)
 *
 * Production Analogy: Like finding the minimum log time window that contains all required
 * event types for incident correlation in observability systems.
 */
public class Problem12_MinimumWindowSubstring {
    public String minWindow(String s, String t) {
        if (t.isEmpty()) return "";
        Map<Character, Integer> need = new HashMap<>(), have = new HashMap<>();
        for (char c : t.toCharArray()) need.merge(c, 1, Integer::sum);
        int required = need.size(), formed = 0;
        int left = 0, minLen = Integer.MAX_VALUE, minStart = 0;
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            have.merge(c, 1, Integer::sum);
            if (need.containsKey(c) && have.get(c).intValue() == need.get(c).intValue()) formed++;
            while (formed == required) {
                if (right - left + 1 < minLen) {
                    minLen = right - left + 1;
                    minStart = left;
                }
                char lc = s.charAt(left);
                have.merge(lc, -1, Integer::sum);
                if (need.containsKey(lc) && have.get(lc) < need.get(lc)) formed--;
                left++;
            }
        }
        return minLen == Integer.MAX_VALUE ? "" : s.substring(minStart, minStart + minLen);
    }

    public static void main(String[] args) {
        Problem12_MinimumWindowSubstring sol = new Problem12_MinimumWindowSubstring();
        System.out.println(sol.minWindow("ADOBECODEBANC", "ABC")); // "BANC"
        System.out.println(sol.minWindow("a", "a")); // "a"
        System.out.println(sol.minWindow("a", "aa")); // ""
        System.out.println(sol.minWindow("aa", "aa")); // "aa"
    }
}
