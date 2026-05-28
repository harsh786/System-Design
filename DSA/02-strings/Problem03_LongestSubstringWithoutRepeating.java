import java.util.*;

/**
 * Problem 3: Longest Substring Without Repeating Characters (LeetCode 3)
 * 
 * Approach 1 (Brute): Check all substrings. O(n^3) time.
 * Approach 2 (Optimal): Sliding window with HashSet/HashMap. O(n) time, O(min(n,m)) space.
 * 
 * Production Analogy: Like finding the longest streak of unique page visits in a user
 * session - you slide a window and shrink from left when you see a repeat.
 */
public class Problem03_LongestSubstringWithoutRepeating {

    public static int lengthOfLongestSubstring(String s) {
        Map<Character, Integer> map = new HashMap<>();
        int left = 0, max = 0;
        for (int right = 0; right < s.length(); right++) {
            char c = s.charAt(right);
            if (map.containsKey(c)) {
                left = Math.max(left, map.get(c) + 1);
            }
            map.put(c, right);
            max = Math.max(max, right - left + 1);
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(lengthOfLongestSubstring("abcabcbb")); // 3
        System.out.println(lengthOfLongestSubstring("bbbbb"));    // 1
        System.out.println(lengthOfLongestSubstring("pwwkew"));   // 3
        System.out.println(lengthOfLongestSubstring(""));          // 0
        System.out.println(lengthOfLongestSubstring(" "));         // 1
    }
}
