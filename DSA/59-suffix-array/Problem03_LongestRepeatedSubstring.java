import java.util.*;

public class Problem03_LongestRepeatedSubstring {
    // Using suffix array + LCP
    public static String longestRepeated(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        int maxLen = 0; String result = "";
        for (int i = 1; i < n; i++) {
            int lcp = lcp(s, sa[i-1], sa[i]);
            if (lcp > maxLen) { maxLen = lcp; result = s.substring(sa[i], sa[i] + lcp); }
        }
        return result;
    }

    static int lcp(String s, int i, int j) {
        int len = 0;
        while (i+len < s.length() && j+len < s.length() && s.charAt(i+len) == s.charAt(j+len)) len++;
        return len;
    }

    public static void main(String[] args) {
        System.out.println(longestRepeated("banana")); // ana
        System.out.println(longestRepeated("aabaabaab")); // aab (or aabaa)
    }
}
