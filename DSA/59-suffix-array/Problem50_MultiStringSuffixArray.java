import java.util.*;

public class Problem50_MultiStringSuffixArray {
    // Generalized suffix array for multiple strings
    public static void buildGeneralizedSA(String[] strings) {
        // Concatenate with unique separators
        StringBuilder sb = new StringBuilder();
        int[] origin = new int[1000000]; // which string each position belongs to
        int pos = 0;
        for (int s = 0; s < strings.length; s++) {
            for (int i = 0; i < strings[s].length(); i++) { origin[pos++] = s; }
            origin[pos++] = -1; // separator
            sb.append(strings[s]);
            sb.append((char)('$' - s - 1)); // unique separator
        }
        String combined = sb.toString();
        int n = combined.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++) sa[i]=i;
        Arrays.sort(sa,(a,b)->combined.substring(a).compareTo(combined.substring(b)));

        System.out.println("Generalized Suffix Array:");
        for (int i = 0; i < Math.min(n, 15); i++) {
            int orig = origin[sa[i]];
            String suffix = combined.substring(sa[i]).replaceAll("[\\x00-\\x1f]", "#");
            System.out.printf("SA[%d]=%d (str %d): %s%n", i, sa[i], orig, suffix.substring(0, Math.min(20, suffix.length())));
        }
    }

    // Find longest common substring of all strings
    public static String longestCommonOfAll(String[] strings) {
        if (strings.length == 1) return strings[0];
        String result = "";
        // Use first two, then intersect with rest
        String common = longestCommon(strings[0], strings[1]);
        for (int i = 2; i < strings.length && !common.isEmpty(); i++)
            common = longestCommon(common, strings[i]);
        return common;
    }

    static String longestCommon(String s1, String s2) {
        String s = s1 + "\0" + s2;
        int n = s.length(), sep = s1.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        int best=0; String result="";
        for(int i=1;i<n;i++){
            if((sa[i-1]<sep)==(sa[i]<sep))continue;
            int lcp=0,a=sa[i-1],b=sa[i]; while(a+lcp<n&&b+lcp<n&&s.charAt(a+lcp)==s.charAt(b+lcp))lcp++;
            if(lcp>best){best=lcp;result=s.substring(sa[i],sa[i]+lcp);}
        }
        return result;
    }

    public static void main(String[] args) {
        String[] strings = {"abcxyz", "xyzabc", "bcxyz"};
        buildGeneralizedSA(strings);
        System.out.println("\nLongest common substring of all: " + longestCommonOfAll(strings));
    }
}
