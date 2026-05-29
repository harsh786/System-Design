package numbertheory;

/**
 * Problem 17: Prime Palindrome (LeetCode 866)
 * 
 * Approach: Generate palindromes in increasing order, check if prime.
 * All even-length palindromes (except 11) are divisible by 11.
 * 
 * Time Complexity: O(n^0.5) per primality check, generating palindromes
 * Space Complexity: O(1)
 */
public class Problem17_PrimePalindrome {
    
    public int primePalindrome(int n) {
        if (n <= 2) return 2;
        if (n <= 3) return 3;
        if (n <= 5) return 5;
        if (n <= 7) return 7;
        if (n <= 11) return 11;
        // Generate odd-length palindromes
        for (int len = 1; ; len++) {
            // Generate palindromes of length 2*len+1
            int start = (int) Math.pow(10, len - 1), end = (int) Math.pow(10, len);
            for (int i = start; i < end; i++) {
                String s = Integer.toString(i);
                String rev = new StringBuilder(s.substring(0, s.length() - 1)).reverse().toString();
                int pal = Integer.parseInt(s + rev);
                if (pal >= n && isPrime(pal)) return pal;
            }
        }
    }
    
    private boolean isPrime(int n) {
        if (n < 2) return false;
        if (n < 4) return true;
        if (n % 2 == 0 || n % 3 == 0) return false;
        for (int i = 5; i * i <= n; i += 6)
            if (n % i == 0 || n % (i + 2) == 0) return false;
        return true;
    }
    
    public static void main(String[] args) {
        Problem17_PrimePalindrome sol = new Problem17_PrimePalindrome();
        System.out.println(sol.primePalindrome(6));   // 7
        System.out.println(sol.primePalindrome(13));  // 101
    }
}
