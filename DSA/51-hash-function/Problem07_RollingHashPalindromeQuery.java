import java.util.*;

public class Problem07_RollingHashPalindromeQuery {
    private static final long MOD = 1_000_000_007;
    private static final long BASE = 31;
    private long[] forwardHash, reverseHash, pow;

    public void preprocess(String s) {
        int n = s.length();
        forwardHash = new long[n + 1];
        reverseHash = new long[n + 1];
        pow = new long[n + 1];
        pow[0] = 1;
        for (int i = 1; i <= n; i++) pow[i] = pow[i-1] * BASE % MOD;
        for (int i = 0; i < n; i++) forwardHash[i+1] = (forwardHash[i] * BASE + s.charAt(i) - 'a' + 1) % MOD;
        for (int i = n - 1; i >= 0; i--) reverseHash[n-i] = (reverseHash[n-i-1] * BASE + s.charAt(i) - 'a' + 1) % MOD;
    }

    public boolean isPalindrome(String s, int l, int r) {
        int n = s.length();
        long fwd = (forwardHash[r+1] - forwardHash[l] * pow[r-l+1] % MOD + MOD * MOD) % MOD;
        long rev = (reverseHash[n-l] - reverseHash[n-r-1] * pow[r-l+1] % MOD + MOD * MOD) % MOD;
        return fwd == rev;
    }

    public static void main(String[] args) {
        Problem07_RollingHashPalindromeQuery sol = new Problem07_RollingHashPalindromeQuery();
        String s = "abacaba";
        sol.preprocess(s);
        System.out.println("Is [0,6] palindrome? " + sol.isPalindrome(s, 0, 6)); // true
        System.out.println("Is [0,3] palindrome? " + sol.isPalindrome(s, 0, 3)); // false
    }
}
