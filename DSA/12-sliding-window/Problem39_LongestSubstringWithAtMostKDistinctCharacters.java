import java.util.*;
/**
 * Problem 39: Longest Substring with At Most K Distinct Characters (LeetCode 340)
 * 
 * Approach: Sliding window with HashMap tracking char frequencies.
 * Window invariant: distinct characters in window <= k.
 * 
 * Time: O(n), Space: O(k)
 * 
 * Production Analogy: Like finding the longest session with at most K unique
 * page types visited for user behavior analysis.
 */
public class Problem39_LongestSubstringWithAtMostKDistinctCharacters {
    public static int lengthOfLongestSubstringKDistinct(String s, int k) {
        if (k == 0) return 0;
        Map<Character, Integer> map = new HashMap<>();
        int left = 0, maxLen = 0;
        for (int right = 0; right < s.length(); right++) {
            map.merge(s.charAt(right), 1, Integer::sum);
            while (map.size() > k) {
                char lc = s.charAt(left);
                map.merge(lc, -1, Integer::sum);
                if (map.get(lc) == 0) map.remove(lc);
                left++;
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(lengthOfLongestSubstringKDistinct("eceba", 2));   // 3
        System.out.println(lengthOfLongestSubstringKDistinct("aa", 1));      // 2
        System.out.println(lengthOfLongestSubstringKDistinct("abcdef", 3)); // 3
    }
}
