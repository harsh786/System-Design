import java.util.*;

/**
 * Problem 4: Longest Substring Without Repeating Characters
 * Given a string, find the length of the longest substring without repeating characters.
 *
 * Approach: Sliding window with HashMap storing last seen index of each character.
 * When duplicate found, move left pointer to max(left, lastSeen+1).
 *
 * Time Complexity: O(n)
 * Space Complexity: O(min(n, charset_size))
 *
 * Production Analogy: Like session window management in stream processing.
 * Track unique events in a sliding window; when duplicate detected, slide window forward.
 */
public class Problem04_LongestSubstringWithoutRepeating {
    public int lengthOfLongestSubstring(String s) {
        Map<Character, Integer> map = new HashMap<>();
        int maxLen = 0, left = 0;
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            if (map.containsKey(c)) {
                left = Math.max(left, map.get(c) + 1);
            }
            map.put(c, right);
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        Problem04_LongestSubstringWithoutRepeating sol = new Problem04_LongestSubstringWithoutRepeating();
        System.out.println(sol.lengthOfLongestSubstring("abcabcbb")); // 3
        System.out.println(sol.lengthOfLongestSubstring("bbbbb")); // 1
        System.out.println(sol.lengthOfLongestSubstring("pwwkew")); // 3
        System.out.println(sol.lengthOfLongestSubstring("")); // 0
        System.out.println(sol.lengthOfLongestSubstring("abcdef")); // 6
    }
}
