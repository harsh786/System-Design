import java.util.*;

public class Problem06_RabinKarpSubstringSearch {
    private static final long BASE = 256;
    private static final long MOD = 101;

    public int search(String text, String pattern) {
        int n = text.length(), m = pattern.length();
        if (m > n) return -1;
        long patHash = 0, txtHash = 0, h = 1;
        for (int i = 0; i < m - 1; i++) h = (h * BASE) % MOD;
        for (int i = 0; i < m; i++) {
            patHash = (BASE * patHash + pattern.charAt(i)) % MOD;
            txtHash = (BASE * txtHash + text.charAt(i)) % MOD;
        }
        for (int i = 0; i <= n - m; i++) {
            if (patHash == txtHash && text.substring(i, i + m).equals(pattern)) return i;
            if (i < n - m) {
                txtHash = (BASE * (txtHash - text.charAt(i) * h) + text.charAt(i + m)) % MOD;
                if (txtHash < 0) txtHash += MOD;
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        Problem06_RabinKarpSubstringSearch sol = new Problem06_RabinKarpSubstringSearch();
        System.out.println("Found at index: " + sol.search("hello world", "world")); // 6
    }
}
