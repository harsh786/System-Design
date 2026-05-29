import java.util.*;

public class Problem23_ShortestPalindromeHash {
    public String shortestPalindrome(String s) {
        long BASE = 31, MOD = 1_000_000_007L;
        long forwardHash = 0, reverseHash = 0, power = 1;
        int best = 0;
        for (int i = 0; i < s.length(); i++) {
            forwardHash = (forwardHash * BASE + s.charAt(i)) % MOD;
            reverseHash = (reverseHash + s.charAt(i) * power) % MOD;
            power = power * BASE % MOD;
            if (forwardHash == reverseHash) best = i;
        }
        String suffix = s.substring(best + 1);
        return new StringBuilder(suffix).reverse().toString() + s;
    }

    public static void main(String[] args) {
        Problem23_ShortestPalindromeHash sol = new Problem23_ShortestPalindromeHash();
        System.out.println(sol.shortestPalindrome("aacecaaa")); // "aaacecaaa"
    }
}
