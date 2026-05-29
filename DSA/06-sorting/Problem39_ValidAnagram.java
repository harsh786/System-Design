import java.util.*;

/**
 * Problem 39: Valid Anagram
 * 
 * Determine if two strings are anagrams.
 * 
 * Approach: Character frequency count comparison.
 * Time Complexity: O(n)
 * Space Complexity: O(1) - fixed 26 chars
 * 
 * Production Analogy: Checksum validation - two data payloads are equivalent if their
 * character/byte distributions match (simplified content-addressable storage check).
 */
public class Problem39_ValidAnagram {
    
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
    
    // Unicode version
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
        Problem39_ValidAnagram sol = new Problem39_ValidAnagram();
        
        System.out.println("Test 1: " + sol.isAnagram("anagram", "nagaram")); // true
        System.out.println("Test 2: " + sol.isAnagram("rat", "car")); // false
        System.out.println("Test 3: " + sol.isAnagram("", "")); // true
        System.out.println("Test 4: " + sol.isAnagram("a", "ab")); // false
        System.out.println("Test 5: " + sol.isAnagramUnicode("café", "facé")); // true
    }
}
