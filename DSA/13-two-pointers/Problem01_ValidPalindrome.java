/**
 * Problem 1: Valid Palindrome
 * 
 * Given a string s, return true if it is a palindrome, considering only
 * alphanumeric characters and ignoring cases.
 * 
 * Approach: Two pointers from both ends, skip non-alphanumeric, compare.
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like a URL canonicalization service that strips special
 * characters before comparing if two URLs are equivalent (forward vs reverse).
 */
public class Problem01_ValidPalindrome {
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
        System.out.println(isPalindrome(" ")); // true
        System.out.println(isPalindrome("")); // true
        System.out.println(isPalindrome("0P")); // false
    }
}
