import java.util.*;
/**
 * Problem 40: Longest Substring with At Most Two Distinct Characters (LeetCode 159)
 * 
 * Approach: Same as Problem 39 with k=2.
 * Window invariant: at most 2 distinct characters in window.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest period where traffic comes from
 * at most 2 regions for simplified routing decisions.
 */
public class Problem40_LongestSubstringWithAtMostTwoDistinctCharacters {
    public static int lengthOfLongestSubstringTwoDistinct(String s) {
        Map<Character, Integer> map = new HashMap<>();
        int left = 0, maxLen = 0;
        for (int right = 0; right < s.length(); right++) {
            map.merge(s.charAt(right), 1, Integer::sum);
            while (map.size() > 2) {
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
        System.out.println(lengthOfLongestSubstringTwoDistinct("eceba"));    // 3
        System.out.println(lengthOfLongestSubstringTwoDistinct("ccaabbb"));  // 5
        System.out.println(lengthOfLongestSubstringTwoDistinct("a"));        // 1
    }
}
