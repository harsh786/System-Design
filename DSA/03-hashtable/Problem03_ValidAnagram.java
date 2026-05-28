import java.util.*;

/**
 * Problem 3: Valid Anagram
 * Determine if two strings are anagrams of each other.
 *
 * Approach: Count character frequencies using HashMap (or int[26] for lowercase).
 * Increment for s, decrement for t. All counts should be zero.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1) - at most 26 characters
 *
 * Production Analogy: Data integrity verification - ensuring a transformed payload
 * contains exactly the same components as the original (like checksum validation).
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

    // Unicode-safe version using HashMap
    public boolean isAnagramUnicode(String s, String t) {
        if (s.length() != t.length()) return false;
        Map<Character, Integer> map = new HashMap<>();
        for (char c : s.toCharArray()) map.merge(c, 1, Integer::sum);
        for (char c : t.toCharArray()) {
            map.merge(c, -1, Integer::sum);
            if (map.get(c) < 0) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        Problem03_ValidAnagram sol = new Problem03_ValidAnagram();
        System.out.println(sol.isAnagram("anagram", "nagaram")); // true
        System.out.println(sol.isAnagram("rat", "car")); // false
        System.out.println(sol.isAnagram("", "")); // true
        System.out.println(sol.isAnagram("a", "ab")); // false
        System.out.println(sol.isAnagramUnicode("anagram", "nagaram")); // true
    }
}
