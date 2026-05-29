import java.util.*;

public class Problem22_SuffixArrayForDNAAlignment {
    public static String longestCommonSubstring(String dna1, String dna2) {
        String s = dna1 + "$" + dna2;
        int n = s.length(), sep = dna1.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++) sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        int best = 0; String result = "";
        for (int i = 1; i < n; i++) {
            if ((sa[i-1]<sep) == (sa[i]<sep)) continue;
            int lcp = 0; int a=sa[i-1],b=sa[i];
            while(a+lcp<n&&b+lcp<n&&s.charAt(a+lcp)==s.charAt(b+lcp)) lcp++;
            if (lcp > best) { best = lcp; result = s.substring(sa[i],sa[i]+lcp); }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(longestCommonSubstring("AGATCGATCG", "TCGATCGATC")); // GATCGATC or similar
    }
}
