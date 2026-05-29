import java.util.*;

public class Problem32_LongestPalindromicSubstringSALCP {
    // Concatenate s + "#" + reverse(s), find longest common prefix across boundary
    public static String longestPalindrome(String s) {
        String rev = new StringBuilder(s).reverse().toString();
        String combined = s + "#" + rev;
        int n = combined.length(), sLen = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->combined.substring(a).compareTo(combined.substring(b)));
        // For each pair of adjacent suffixes from different halves, check if they form palindrome
        String best = s.substring(0,1);
        for (int i = 1; i < n; i++) {
            boolean fromS = sa[i] < sLen, prevFromS = sa[i-1] < sLen;
            if (fromS == prevFromS) continue;
            int lcp = 0, a=sa[i-1],b=sa[i];
            while(a+lcp<n&&b+lcp<n&&combined.charAt(a+lcp)==combined.charAt(b+lcp))lcp++;
            if (lcp > best.length()) {
                int start = fromS ? sa[i] : sa[i-1];
                String cand = s.substring(start, start+lcp);
                if (cand.equals(new StringBuilder(cand).reverse().toString())) best = cand;
            }
        }
        return best;
    }

    public static void main(String[] args) {
        System.out.println(longestPalindrome("babad")); // bab or aba
        System.out.println(longestPalindrome("cbbd")); // bb
    }
}
