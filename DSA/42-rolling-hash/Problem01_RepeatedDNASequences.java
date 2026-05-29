import java.util.*;

// Repeated DNA Sequences
public class Problem01_RepeatedDNASequences {
    static final long MOD = 1_000_000_007L;
    static final long BASE = 31L;

    static long[] computeHash(String s) {
        int n = s.length();
        long[] h = new long[n + 1];
        long[] pw = new long[n + 1];
        pw[0] = 1;
        for (int i = 0; i < n; i++) {
            h[i + 1] = (h[i] * BASE + (s.charAt(i) - 'a' + 1)) % MOD;
            pw[i + 1] = pw[i] * BASE % MOD;
        }
        return h;
    }

    static long getHash(long[] h, long[] pw, int l, int r) {
        return (h[r + 1] - h[l] * pw[r - l + 1] % MOD + MOD * MOD) % MOD;
    }

    static int rabinKarp(String text, String pattern) {
        int n = text.length(), m = pattern.length();
        if (m > n) return -1;
        long patHash = 0, textHash = 0, power = 1;
        for (int i = 0; i < m; i++) {
            patHash = (patHash * BASE + (pattern.charAt(i) - 'a' + 1)) % MOD;
            textHash = (textHash * BASE + (text.charAt(i) - 'a' + 1)) % MOD;
            if (i > 0) power = power * BASE % MOD;
        }
        if (textHash == patHash && text.substring(0, m).equals(pattern)) return 0;
        for (int i = 1; i <= n - m; i++) {
            textHash = (textHash - (text.charAt(i - 1) - 'a' + 1) * power % MOD + MOD) % MOD;
            textHash = (textHash * BASE + (text.charAt(i + m - 1) - 'a' + 1)) % MOD;
            if (textHash == patHash && text.substring(i, i + m).equals(pattern)) return i;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println("Repeated DNA Sequences");
        String text = "abcabcabc";
        String pattern = "cab";
        int idx = rabinKarp(text, pattern);
        System.out.println("Pattern found at index: " + idx);
        long[] h = computeHash(text);
        long[] pw = new long[text.length() + 1];
        pw[0] = 1;
        for (int i = 1; i <= text.length(); i++) pw[i] = pw[i-1] * BASE % MOD;
        System.out.println("Hash of [0..2]: " + getHash(h, pw, 0, 2));
    }
}
