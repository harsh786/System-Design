/**
 * Problem 1: Palindrome Number
 * Determine whether an integer is a palindrome without converting to string.
 *
 * Approach: Reverse half the number and compare with the other half.
 * Mathematical Insight: We only need to reverse half the digits to avoid overflow.
 * Time Complexity: O(log10(n)) - we process half the digits
 * Space Complexity: O(1)
 *
 * Production Analogy: Like validating symmetric checksums in network packets -
 * you can compare from both ends without storing the entire payload.
 */
public class Problem01_PalindromeNumber {

    public static boolean isPalindrome(int x) {
        // Negative numbers and numbers ending in 0 (except 0 itself) are not palindromes
        if (x < 0 || (x % 10 == 0 && x != 0)) return false;

        int reversed = 0;
        while (x > reversed) {
            reversed = reversed * 10 + x % 10;
            x /= 10;
        }
        // For odd-length numbers, we can get rid of the middle digit by reversed/10
        return x == reversed || x == reversed / 10;
    }

    public static void main(String[] args) {
        System.out.println(isPalindrome(121));       // true
        System.out.println(isPalindrome(-121));      // false
        System.out.println(isPalindrome(10));        // false
        System.out.println(isPalindrome(0));         // true
        System.out.println(isPalindrome(12321));     // true
        System.out.println(isPalindrome(1234321));   // true
        System.out.println(isPalindrome(Integer.MAX_VALUE)); // false
    }
}
