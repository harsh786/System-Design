import java.util.*;

public class Problem22_DistinctEchoSubstrings {
    public int distinctEchoSubstrings(String text) {
        int n = text.length();
        Set<String> result = new HashSet<>();
        long BASE = 31, MOD = 1_000_000_007L;
        for (int len = 1; len <= n / 2; len++) {
            long h1 = 0, h2 = 0, pow = 1;
            for (int i = 0; i < len; i++) { h1 = (h1 * BASE + text.charAt(i)) % MOD; pow = (i > 0) ? pow * BASE % MOD : 1; }
            for (int i = len; i < 2 * len; i++) h2 = (h2 * BASE + text.charAt(i)) % MOD;
            if (h1 == h2 && text.substring(0, len).equals(text.substring(len, 2*len))) result.add(text.substring(0, 2*len));
            for (int i = 1; i + 2 * len <= n; i++) {
                h1 = ((h1 - text.charAt(i-1) * pow % MOD + MOD) * BASE + text.charAt(i+len-1)) % MOD;
                h2 = ((h2 - text.charAt(i+len-1) * pow % MOD + MOD) * BASE + text.charAt(i+2*len-1)) % MOD;
                if (h1 == h2) {
                    String s1 = text.substring(i, i+len), s2 = text.substring(i+len, i+2*len);
                    if (s1.equals(s2)) result.add(s1 + s2);
                }
            }
        }
        return result.size();
    }

    public static void main(String[] args) {
        Problem22_DistinctEchoSubstrings sol = new Problem22_DistinctEchoSubstrings();
        System.out.println(sol.distinctEchoSubstrings("abcabcabc")); // 3
    }
}
