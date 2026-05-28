import java.util.*;

/**
 * Problem 37: Ransom Note (LeetCode 383)
 * 
 * Approach: Count chars in magazine, check if sufficient for ransom note. O(n) time, O(1) space.
 * 
 * Production Analogy: Like checking if available inventory covers all items in an order.
 */
public class Problem37_RansomNote {

    public static boolean canConstruct(String ransomNote, String magazine) {
        int[] count = new int[26];
        for (char c : magazine.toCharArray()) count[c - 'a']++;
        for (char c : ransomNote.toCharArray()) {
            if (--count[c - 'a'] < 0) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(canConstruct("a", "b"));   // false
        System.out.println(canConstruct("aa", "ab")); // false
        System.out.println(canConstruct("aa", "aab")); // true
    }
}
