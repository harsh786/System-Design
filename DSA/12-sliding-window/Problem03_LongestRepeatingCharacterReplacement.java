/**
 * Problem 3: Longest Repeating Character Replacement (LeetCode 424)
 * 
 * Approach: Sliding window tracking frequency of most common char in window.
 * Window invariant: (window size - max freq char count) <= k
 * If violated, shrink from left.
 * 
 * Time: O(n), Space: O(26) = O(1)
 * 
 * Production Analogy: Like error budget in SRE - you can tolerate k "different"
 * events in a window before triggering an alert.
 */
public class Problem03_LongestRepeatingCharacterReplacement {
    public static int characterReplacement(String s, int k) {
        int[] count = new int[26];
        int left = 0, maxCount = 0, maxLen = 0;
        for (int right = 0; right < s.length(); right++) {
            count[s.charAt(right) - 'A']++;
            maxCount = Math.max(maxCount, count[s.charAt(right) - 'A']);
            // Window size - maxCount > k means too many replacements needed
            if ((right - left + 1) - maxCount > k) {
                count[s.charAt(left) - 'A']--;
                left++;
            }
            maxLen = Math.max(maxLen, right - left + 1);
        }
        return maxLen;
    }

    public static void main(String[] args) {
        System.out.println(characterReplacement("ABAB", 2));    // 4
        System.out.println(characterReplacement("AABABBA", 1)); // 4
        System.out.println(characterReplacement("AAAA", 0));    // 4
        System.out.println(characterReplacement("ABCD", 2));    // 3
        System.out.println(characterReplacement("", 1));         // 0
    }
}
