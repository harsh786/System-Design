/**
 * Problem: First Unique Character in a String (LeetCode 387)
 * Approach: Two-pass counting
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Finding unique identifiers in streaming data
 */
public class Problem05_FirstUniqueCharacter {
    public int firstUniqChar(String s) {
        int[] count = new int[26];
        for (char c : s.toCharArray()) count[c-'a']++;
        for (int i = 0; i < s.length(); i++) if (count[s.charAt(i)-'a'] == 1) return i;
        return -1;
    }
    public static void main(String[] args) {
        System.out.println(new Problem05_FirstUniqueCharacter().firstUniqChar("loveleetcode")); // 2
    }
}
