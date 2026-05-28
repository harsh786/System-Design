import java.util.*;

/**
 * Problem 4: Longest Repeating Character Replacement (LeetCode 424)
 * 
 * Given string s and int k, find longest substring where you can replace at most k chars
 * to make all chars the same.
 * 
 * Approach: Sliding window. Track max frequency in window. If window_size - maxFreq > k, shrink.
 * O(n) time, O(1) space.
 * 
 * Production Analogy: Like finding the longest period where a server was "mostly healthy"
 * (allowing k unhealthy minutes to be ignored).
 */
public class Problem04_LongestRepeatingCharacterReplacement {

    public static int characterReplacement(String s, int k) {
        int[] count = new int[26];
        int left = 0, maxFreq = 0, result = 0;
        for (int right = 0; right < s.length(); right++) {
            count[s.charAt(right) - 'A']++;
            maxFreq = Math.max(maxFreq, count[s.charAt(right) - 'A']);
            while (right - left + 1 - maxFreq > k) {
                count[s.charAt(left) - 'A']--;
                left++;
            }
            result = Math.max(result, right - left + 1);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(characterReplacement("ABAB", 2));    // 4
        System.out.println(characterReplacement("AABABBA", 1)); // 4
        System.out.println(characterReplacement("A", 0));       // 1
        System.out.println(characterReplacement("AAAA", 2));    // 4
    }
}
