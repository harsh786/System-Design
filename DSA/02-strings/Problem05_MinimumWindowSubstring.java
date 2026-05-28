import java.util.*;

/**
 * Problem 5: Minimum Window Substring (LeetCode 76)
 * 
 * Given strings s and t, find the minimum window in s that contains all chars of t.
 * 
 * Approach: Sliding window with two pointers. Expand right to satisfy, shrink left to minimize.
 * O(|s| + |t|) time, O(|s| + |t|) space.
 * 
 * Production Analogy: Like finding the shortest log segment that contains all required
 * error codes for a complete diagnosis.
 */
public class Problem05_MinimumWindowSubstring {

    public static String minWindow(String s, String t) {
        if (s.length() < t.length()) return "";
        Map<Character, Integer> need = new HashMap<>(), have = new HashMap<>();
        for (char c : t.toCharArray()) need.merge(c, 1, Integer::sum);
        
        int required = need.size(), formed = 0;
        int left = 0, minLen = Integer.MAX_VALUE, minLeft = 0;
        
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            have.merge(c, 1, Integer::sum);
            if (need.containsKey(c) && have.get(c).intValue() == need.get(c).intValue()) formed++;
            
            while (formed == required) {
                if (right - left + 1 < minLen) {
                    minLen = right - left + 1;
                    minLeft = left;
                }
                char lc = s.charAt(left);
                have.merge(lc, -1, Integer::sum);
                if (need.containsKey(lc) && have.get(lc) < need.get(lc)) formed--;
                left++;
            }
        }
        return minLen == Integer.MAX_VALUE ? "" : s.substring(minLeft, minLeft + minLen);
    }

    public static void main(String[] args) {
        System.out.println(minWindow("ADOBECODEBANC", "ABC")); // "BANC"
        System.out.println(minWindow("a", "a"));               // "a"
        System.out.println(minWindow("a", "aa"));              // ""
    }
}
