/**
 * Problem 4: Permutation in String (LeetCode 567)
 * 
 * Approach: Fixed-size sliding window of length s1. Track char frequency match.
 * Window invariant: window size == s1.length(), check if frequencies match.
 * 
 * Time: O(n), Space: O(26) = O(1)
 * 
 * Production Analogy: Like detecting a specific pattern of API calls (in any order)
 * within a fixed time window for fraud detection.
 */
public class Problem04_PermutationInString {
    public static boolean checkInclusion(String s1, String s2) {
        if (s1.length() > s2.length()) return false;
        int[] count = new int[26];
        for (char c : s1.toCharArray()) count[c - 'a']++;
        int[] window = new int[26];
        for (int i = 0; i < s2.length(); i++) {
            window[s2.charAt(i) - 'a']++;
            if (i >= s1.length()) {
                window[s2.charAt(i - s1.length()) - 'a']--;
            }
            if (java.util.Arrays.equals(count, window)) return true;
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(checkInclusion("ab", "eidbaooo")); // true
        System.out.println(checkInclusion("ab", "eidboaoo")); // false
        System.out.println(checkInclusion("a", "a"));          // true
        System.out.println(checkInclusion("abc", "bca"));      // true
        System.out.println(checkInclusion("hello", "ooolleoooleh")); // false
    }
}
