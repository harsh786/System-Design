import java.util.*;

public class Problem04_DistinctSubstringsCount {
    // Total substrings = n*(n+1)/2, minus sum of LCP values
    public static int countDistinct(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        int total = n * (n + 1) / 2;
        for (int i = 1; i < n; i++) {
            int lcp = 0, a = sa[i-1], b = sa[i];
            while (a+lcp < n && b+lcp < n && s.charAt(a+lcp) == s.charAt(b+lcp)) lcp++;
            total -= lcp;
        }
        return total;
    }

    public static void main(String[] args) {
        System.out.println(countDistinct("banana")); // 15
        System.out.println(countDistinct("abc")); // 6
    }
}
