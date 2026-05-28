import java.util.*;

/**
 * Problem 3: Valid Anagram
 * Given two strings s and t, return true if t is an anagram of s.
 *
 * Approach: Count character frequencies. If all counts are zero after processing both strings, they're anagrams.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1) - fixed 26-char array
 *
 * Production Analogy: Like checksum verification in data transfer.
 * Two packets with same checksum (frequency signature) contain equivalent data.
 */
public class Problem03_ValidAnagram {
    public boolean isAnagram(String s, String t) {
        if (s.length() != t.length()) return false;
        int[] count = new int[26];
        for (int i = 0; i < s.length(); i++) {
            count[s.charAt(i) - 'a']++;
            count[t.charAt(i) - 'a']--;
        }
        for (int c : count) if (c != 0) return false;
        return true;
    }

    public static void main(String[] args) {
        Problem03_ValidAnagram sol = new Problem03_ValidAnagram();
        System.out.println(sol.isAnagram("anagram", "nagaram")); // true
        System.out.println(sol.isAnagram("rat", "car")); // false
        System.out.println(sol.isAnagram("", "")); // true
        System.out.println(sol.isAnagram("a", "ab")); // false
    }
}
