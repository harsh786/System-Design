import java.util.*;

public class Problem47_MaximalPalindromes {
    // Manacher's algorithm for all maximal palindromes
    public static int[] manacher(String s) {
        // Transform: "abc" -> "^#a#b#c#$"
        StringBuilder t = new StringBuilder("^#");
        for (char c : s.toCharArray()) { t.append(c); t.append('#'); }
        t.append('$');
        int[] p = new int[t.length()];
        int c = 0, r = 0;
        for (int i = 1; i < t.length()-1; i++) {
            int mirror = 2*c - i;
            if (i < r) p[i] = Math.min(r-i, p[mirror]);
            while (t.charAt(i+p[i]+1) == t.charAt(i-p[i]-1)) p[i]++;
            if (i + p[i] > r) { c = i; r = i + p[i]; }
        }
        // Extract palindrome lengths for original string
        int[] result = new int[s.length()];
        for (int i = 0; i < s.length(); i++) result[i] = p[2*i+2]; // centered at i (odd length)
        return result;
    }

    public static void main(String[] args) {
        String s = "abacaba";
        int[] p = manacher(s);
        System.out.println("Palindrome radii: " + Arrays.toString(p));
        // Find longest
        int maxIdx = 0;
        for (int i = 1; i < p.length; i++) if (p[i] > p[maxIdx]) maxIdx = i;
        System.out.println("Longest palindrome: " + s.substring(maxIdx-p[maxIdx], maxIdx+p[maxIdx]+1));
    }
}
