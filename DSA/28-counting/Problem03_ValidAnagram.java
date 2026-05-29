/**
 * Problem: Valid Anagram (LeetCode 242)
 * Approach: Character frequency count comparison
 * Complexity: O(n) time, O(1) space (26 chars)
 * Production Analogy: Checksum validation for data integrity
 */
public class Problem03_ValidAnagram {
    public boolean isAnagram(String s, String t) {
        if (s.length() != t.length()) return false;
        int[] count = new int[26];
        for (int i = 0; i < s.length(); i++) { count[s.charAt(i)-'a']++; count[t.charAt(i)-'a']--; }
        for (int c : count) if (c != 0) return false;
        return true;
    }
    public static void main(String[] args) {
        System.out.println(new Problem03_ValidAnagram().isAnagram("anagram", "nagaram")); // true
    }
}
