/**
 * Problem 40: Longest Substring Without Repeating Characters
 * 
 * Find length of longest substring without repeating characters.
 * 
 * Approach: Sliding window with HashSet/HashMap to track chars in window.
 * Time: O(n), Space: O(min(n, charset))
 * 
 * Production Analogy: Like finding the longest stretch of unique session IDs
 * in a request log to measure traffic diversity windows.
 */
import java.util.HashMap;

public class Problem40_LongestSubstringWithoutRepeating {
    public static int lengthOfLongestSubstring(String s) {
        HashMap<Character, Integer> map = new HashMap<>();
        int left = 0, max = 0;
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            if (map.containsKey(c)) left = Math.max(left, map.get(c) + 1);
            map.put(c, right);
            max = Math.max(max, right - left + 1);
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(lengthOfLongestSubstring("abcabcbb")); // 3
        System.out.println(lengthOfLongestSubstring("bbbbb")); // 1
        System.out.println(lengthOfLongestSubstring("pwwkew")); // 3
        System.out.println(lengthOfLongestSubstring("")); // 0
    }
}
