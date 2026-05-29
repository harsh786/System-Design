package numbertheory;

/**
 * Problem 26: Reverse Integer (LeetCode 7)
 * 
 * Approach: Pop digits and check overflow before pushing.
 * 
 * Time Complexity: O(log x)
 * Space Complexity: O(1)
 */
public class Problem26_ReverseInteger {
    
    public int reverse(int x) {
        int rev = 0;
        while (x != 0) {
            int digit = x % 10;
            if (rev > Integer.MAX_VALUE / 10 || rev < Integer.MIN_VALUE / 10) return 0;
            rev = rev * 10 + digit;
            x /= 10;
        }
        return rev;
    }
    
    public static void main(String[] args) {
        Problem26_ReverseInteger sol = new Problem26_ReverseInteger();
        System.out.println(sol.reverse(123));  // 321
        System.out.println(sol.reverse(-123)); // -321
    }
}
