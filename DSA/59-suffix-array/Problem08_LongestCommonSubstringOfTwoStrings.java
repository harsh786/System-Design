import java.util.*;

public class Problem08_LongestCommonSubstringOfTwoStrings {
    // Concatenate with separator, build SA, find max LCP across boundary
    public static String longestCommon(String s1, String s2) {
        String combined = s1 + "#" + s2;
        int n = combined.length(), sep = s1.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> combined.substring(a).compareTo(combined.substring(b)));
        int maxLen = 0; String result = "";
        for (int i = 1; i < n; i++) {
            boolean diff = (sa[i-1] < sep) != (sa[i] < sep);
            if (!diff) continue;
            int lcp = 0;
            while (sa[i-1]+lcp < n && sa[i]+lcp < n && combined.charAt(sa[i-1]+lcp) == combined.charAt(sa[i]+lcp)) lcp++;
            if (lcp > maxLen) { maxLen = lcp; result = combined.substring(sa[i], sa[i]+lcp); }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(longestCommon("abcdef", "zbcdf")); // bcd
        System.out.println(longestCommon("geeksforgeeks", "geeksquiz")); // geeks
    }
}
