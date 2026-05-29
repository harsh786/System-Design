import java.util.*;

public class Problem45_StringPeriodUsingSA {
    // Find smallest period of string using failure function (KMP-like)
    public static int smallestPeriod(String s) {
        int n = s.length();
        int[] fail = new int[n];
        for (int i = 1; i < n; i++) {
            int j = fail[i-1];
            while (j > 0 && s.charAt(i) != s.charAt(j)) j = fail[j-1];
            if (s.charAt(i) == s.charAt(j)) j++;
            fail[i] = j;
        }
        int period = n - fail[n-1];
        return period;
    }

    public static void main(String[] args) {
        System.out.println(smallestPeriod("abcabcabc")); // 3
        System.out.println(smallestPeriod("abababab")); // 2
        System.out.println(smallestPeriod("abcd")); // 4 (no repetition)
    }
}
