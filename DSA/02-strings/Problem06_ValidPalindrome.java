import java.util.*;

/**
 * Problem 6: Valid Palindrome (LeetCode 125)
 * 
 * Check if string is palindrome considering only alphanumeric chars, ignoring case.
 * 
 * Approach: Two pointers from both ends. O(n) time, O(1) space.
 * 
 * Production Analogy: Like validating symmetric configuration (e.g., firewall rules
 * that should mirror inbound/outbound).
 */
public class Problem06_ValidPalindrome {

    public static boolean isPalindrome(String s) {
        int left = 0, right = s.length() - 1;
        while (left < right) {
            while (left < right && !Character.isLetterOrDigit(s.charAt(left))) left++;
            while (left < right && !Character.isLetterOrDigit(s.charAt(right))) right--;
            if (Character.toLowerCase(s.charAt(left)) != Character.toLowerCase(s.charAt(right))) return false;
            left++;
            right--;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(isPalindrome("A man, a plan, a canal: Panama")); // true
        System.out.println(isPalindrome("race a car")); // false
        System.out.println(isPalindrome(" "));          // true
        System.out.println(isPalindrome("0P"));         // false
    }
}
