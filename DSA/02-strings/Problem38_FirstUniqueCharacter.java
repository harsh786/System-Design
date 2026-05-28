import java.util.*;

/**
 * Problem 38: First Unique Character in a String (LeetCode 387)
 * 
 * Approach: Count frequency, then find first with count 1. O(n) time, O(1) space.
 * 
 * Production Analogy: Like finding the first unique request ID in a log to identify
 * a non-retried operation.
 */
public class Problem38_FirstUniqueCharacter {

    public static int firstUniqChar(String s) {
        int[] count = new int[26];
        for (char c : s.toCharArray()) count[c - 'a']++;
        for (int i = 0; i < s.length(); i++) {
            if (count[s.charAt(i) - 'a'] == 1) return i;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(firstUniqChar("leetcode"));     // 0
        System.out.println(firstUniqChar("loveleetcode")); // 2
        System.out.println(firstUniqChar("aabb"));         // -1
    }
}
