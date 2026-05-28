import java.util.*;
/**
 * Problem 2: Longest Substring Without Repeating Characters (LeetCode 3)
 * 
 * Approach: Expanding window with HashSet. Shrink left when duplicate found.
 * Window invariant: all characters in window [left..right] are unique.
 * 
 * Time: O(n), Space: O(min(n, charset))
 * 
 * Production Analogy: Like tracking unique active sessions in a time window
 * for real-time analytics dashboards.
 */
public class Problem02_LongestSubstringWithoutRepeatingCharacters {
    public static int lengthOfLongestSubstring(String s) {
        Map<Character, Integer> map = new HashMap<>();
        int left = 0, maxLen = 0;
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            if (map.containsKey(c) && map.get(c) >= left) {
                left = map.get(c) + 1;
            }
            map.put(c, right);
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(lengthOfLongestSubstring("abcabcbb")); // 3
        System.out.println(lengthOfLongestSubstring("bbbbb"));    // 1
        System.out.println(lengthOfLongestSubstring("pwwkew"));   // 3
        System.out.println(lengthOfLongestSubstring(""));          // 0
        System.out.println(lengthOfLongestSubstring("abcdef"));   // 6
        System.out.println(lengthOfLongestSubstring(" "));         // 1
    }
}
