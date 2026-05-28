import java.util.*;

/**
 * Problem 16: First Unique Character in a String
 * Find the first non-repeating character and return its index.
 *
 * Approach: Count frequencies, then scan string for first char with count 1.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1) - fixed charset
 *
 * Production Analogy: Like finding the first unique transaction ID in a batch
 * for idempotency key assignment.
 */
public class Problem16_FirstUniqueCharacter {
    public int firstUniqChar(String s) {
        int[] count = new int[26];
        for (char c : s.toCharArray()) count[c - 'a']++;
        for (int i = 0; i < s.length(); i++) {
            if (count[s.charAt(i) - 'a'] == 1) return i;
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem16_FirstUniqueCharacter sol = new Problem16_FirstUniqueCharacter();
        System.out.println(sol.firstUniqChar("leetcode")); // 0
        System.out.println(sol.firstUniqChar("loveleetcode")); // 2
        System.out.println(sol.firstUniqChar("aabb")); // -1
        System.out.println(sol.firstUniqChar("")); // -1
    }
}
