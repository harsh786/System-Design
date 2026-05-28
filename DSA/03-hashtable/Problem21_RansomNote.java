import java.util.*;

/**
 * Problem 21: Ransom Note
 * Return true if ransomNote can be constructed from magazine characters.
 *
 * Approach: Count magazine chars, decrement for ransom note chars.
 *
 * Time Complexity: O(m + n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Like resource pool allocation - check if available inventory
 * (magazine) can satisfy a request (ransom note).
 */
public class Problem21_RansomNote {
    public boolean canConstruct(String ransomNote, String magazine) {
        int[] count = new int[26];
        for (char c : magazine.toCharArray()) count[c - 'a']++;
        for (char c : ransomNote.toCharArray()) {
            if (--count[c - 'a'] < 0) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        Problem21_RansomNote sol = new Problem21_RansomNote();
        System.out.println(sol.canConstruct("a", "b")); // false
        System.out.println(sol.canConstruct("aa", "ab")); // false
        System.out.println(sol.canConstruct("aa", "aab")); // true
    }
}
