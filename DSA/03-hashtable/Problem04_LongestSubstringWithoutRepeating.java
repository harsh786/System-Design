import java.util.*;

/**
 * Problem 4: Longest Substring Without Repeating Characters
 * Find the length of the longest substring without repeating characters.
 *
 * Approach: Sliding window with HashMap storing char -> last index.
 * When duplicate found, move left pointer past the previous occurrence.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(min(n, charset_size))
 *
 * Production Analogy: Session uniqueness tracking - like ensuring no duplicate
 * events in a streaming window (Kafka dedup window, unique visitors in time range).
 */
public class Problem04_LongestSubstringWithoutRepeating {
    public int lengthOfLongestSubstring(String s) {
        Map<Character, Integer> map = new HashMap<>();
        int maxLen = 0, left = 0;
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
        Problem04_LongestSubstringWithoutRepeating sol = new Problem04_LongestSubstringWithoutRepeating();
        System.out.println(sol.lengthOfLongestSubstring("abcabcbb")); // 3
        System.out.println(sol.lengthOfLongestSubstring("bbbbb")); // 1
        System.out.println(sol.lengthOfLongestSubstring("pwwkew")); // 3
        System.out.println(sol.lengthOfLongestSubstring("")); // 0
        System.out.println(sol.lengthOfLongestSubstring("abcdef")); // 6
        System.out.println(sol.lengthOfLongestSubstring(" ")); // 1
    }
}
