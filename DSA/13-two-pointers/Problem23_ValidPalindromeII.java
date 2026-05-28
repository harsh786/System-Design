/**
 * Problem 23: Valid Palindrome II
 * 
 * Can we make s a palindrome by deleting at most one character?
 * 
 * Approach: Two pointers; on mismatch, try skipping left or right.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like a fault-tolerant checksum that allows one
 * corrupted byte before flagging data as invalid.
 */
public class Problem23_ValidPalindromeII {
    public static boolean validPalindrome(String s) {
        int left = 0, right = s.length() - 1;
        while (left < right) {
            if (s.charAt(left) != s.charAt(right)) {
                return isPalin(s, left + 1, right) || isPalin(s, left, right - 1);
            }
            left++; right--;
        }
        return true;
    }

    private static boolean isPalin(String s, int l, int r) {
        while (l < r) { if (s.charAt(l++) != s.charAt(r--)) return false; }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(validPalindrome("aba")); // true
        System.out.println(validPalindrome("abca")); // true
        System.out.println(validPalindrome("abc")); // false
    }
}
