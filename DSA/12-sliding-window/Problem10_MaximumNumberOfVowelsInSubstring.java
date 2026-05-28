/**
 * Problem 10: Maximum Number of Vowels in a Substring of Given Length (LeetCode 1456)
 * 
 * Approach: Fixed-size sliding window of size k, count vowels.
 * Window invariant: track vowel count in current window of size k.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting high-priority events in a fixed time bucket
 * for alerting thresholds.
 */
public class Problem10_MaximumNumberOfVowelsInSubstring {
    public static int maxVowels(String s, int k) {
        int vowels = 0;
        for (int i = 0; i < k; i++) {
            if (isVowel(s.charAt(i))) vowels++;
        }
        int max = vowels;
        for (int i = k; i < s.length(); i++) {
            if (isVowel(s.charAt(i))) vowels++;
            if (isVowel(s.charAt(i - k))) vowels--;
            max = Math.max(max, vowels);
        }
        return max;
    }

    private static boolean isVowel(char c) {
        return "aeiou".indexOf(c) >= 0;
    }

    public static void main(String[] args) {
        System.out.println(maxVowels("abciiidef", 3)); // 3
        System.out.println(maxVowels("aeiou", 2));     // 2
        System.out.println(maxVowels("leetcode", 3));  // 2
        System.out.println(maxVowels("rhythms", 4));   // 0
    }
}
