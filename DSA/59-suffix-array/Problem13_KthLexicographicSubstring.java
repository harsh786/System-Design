import java.util.*;

public class Problem13_KthLexicographicSubstring {
    // Find k-th smallest distinct substring using SA + LCP
    public static String kthSubstring(String s, int k) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        int prev = 0; // previous LCP
        int count = 0;
        for (int i = 0; i < n; i++) {
            int lcp = 0;
            if (i > 0) {
                int a = sa[i-1], b = sa[i];
                while (a+lcp < n && b+lcp < n && s.charAt(a+lcp) == s.charAt(b+lcp)) lcp++;
            }
            int newSubstrings = (n - sa[i]) - lcp;
            if (count + newSubstrings >= k) {
                int len = lcp + (k - count);
                return s.substring(sa[i], sa[i] + len);
            }
            count += newSubstrings;
        }
        return "";
    }

    public static void main(String[] args) {
        System.out.println(kthSubstring("banana", 1));  // a
        System.out.println(kthSubstring("banana", 5));  // ana
        System.out.println(kthSubstring("banana", 10)); // ban
    }
}
