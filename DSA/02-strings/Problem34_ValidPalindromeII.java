import java.util.*;

/**
 * Problem 34: Valid Palindrome II (LeetCode 680)
 * 
 * Can become palindrome by removing at most one character.
 * Approach: Two pointers; on mismatch, try skipping left or right. O(n) time, O(1) space.
 * 
 * Production Analogy: Like fault-tolerant validation - allowing one "error" before rejecting.
 */
public class Problem34_ValidPalindromeII {

    public static boolean validPalindrome(String s) {
        int l = 0, r = s.length() - 1;
        while (l < r) {
            if (s.charAt(l) != s.charAt(r)) {
                return isPalin(s, l + 1, r) || isPalin(s, l, r - 1);
            }
            l++; r--;
        }
        return true;
    }

    private static boolean isPalin(String s, int l, int r) {
        while (l < r) { if (s.charAt(l++) != s.charAt(r--)) return false; }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(validPalindrome("aba"));   // true
        System.out.println(validPalindrome("abca"));  // true
        System.out.println(validPalindrome("abc"));   // false
    }
}
