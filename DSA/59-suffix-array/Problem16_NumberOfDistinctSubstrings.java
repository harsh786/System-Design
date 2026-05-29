import java.util.*;

public class Problem16_NumberOfDistinctSubstrings {
    public static long countDistinct(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        long total = (long)n*(n+1)/2;
        for (int i = 1; i < n; i++) {
            int lcp = 0, a = sa[i-1], b = sa[i];
            while (a+lcp<n && b+lcp<n && s.charAt(a+lcp)==s.charAt(b+lcp)) lcp++;
            total -= lcp;
        }
        return total;
    }

    public static void main(String[] args) {
        System.out.println(countDistinct("abab")); // 7: a,ab,aba,abab,b,ba,bab
        System.out.println(countDistinct("abc"));  // 6
    }
}
