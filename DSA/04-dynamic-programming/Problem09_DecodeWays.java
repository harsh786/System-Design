/**
 * Problem 9: Decode Ways
 * 
 * A message encoded as digits. '1'->'A', ..., '26'->'Z'. Count ways to decode.
 * 
 * State: dp[i] = number of ways to decode s[0..i-1]
 * Recurrence: dp[i] += dp[i-1] if s[i-1] != '0'
 *             dp[i] += dp[i-2] if s[i-2..i-1] forms 10-26
 * 
 * Time: O(n), Space: O(1) optimized
 * 
 * Production Analogy: Like parsing variable-length encoded messages where each
 * token can be 1 or 2 bytes, counting valid parse trees.
 */
public class Problem09_DecodeWays {

    public static int numDecodings(String s) {
        if (s.isEmpty() || s.charAt(0) == '0') return 0;
        int n = s.length();
        int prev2 = 1, prev1 = 1;
        for (int i = 1; i < n; i++) {
            int curr = 0;
            if (s.charAt(i) != '0') curr += prev1;
            int twoDigit = Integer.parseInt(s.substring(i - 1, i + 1));
            if (twoDigit >= 10 && twoDigit <= 26) curr += prev2;
            prev2 = prev1;
            prev1 = curr;
        }
        return prev1;
    }

    public static void main(String[] args) {
        System.out.println("=== Decode Ways ===");
        System.out.println(numDecodings("12")); // 2
        System.out.println(numDecodings("226")); // 3
        System.out.println(numDecodings("06")); // 0
        System.out.println(numDecodings("10")); // 1
        System.out.println(numDecodings("27")); // 1
    }
}
