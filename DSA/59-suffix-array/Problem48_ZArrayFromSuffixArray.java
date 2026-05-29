import java.util.*;

public class Problem48_ZArrayFromSuffixArray {
    // Z-array: z[i] = length of longest prefix of s that matches s[i..]
    public static int[] zArray(String s) {
        int n = s.length();
        int[] z = new int[n];
        int l = 0, r = 0;
        for (int i = 1; i < n; i++) {
            if (i < r) z[i] = Math.min(r-i, z[i-l]);
            while (i+z[i] < n && s.charAt(z[i]) == s.charAt(i+z[i])) z[i]++;
            if (i+z[i] > r) { l = i; r = i+z[i]; }
        }
        return z;
    }

    // Pattern matching using Z-array
    public static List<Integer> zSearch(String text, String pattern) {
        String combined = pattern + "$" + text;
        int[] z = zArray(combined);
        List<Integer> result = new ArrayList<>();
        for (int i = pattern.length()+1; i < combined.length(); i++)
            if (z[i] == pattern.length()) result.add(i - pattern.length() - 1);
        return result;
    }

    public static void main(String[] args) {
        System.out.println("Z-array of 'aabxaab': " + Arrays.toString(zArray("aabxaab")));
        System.out.println("Pattern 'ab' in 'ababab': " + zSearch("ababab", "ab"));
    }
}
