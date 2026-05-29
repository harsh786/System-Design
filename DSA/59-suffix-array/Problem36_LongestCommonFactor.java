import java.util.*;

public class Problem36_LongestCommonFactor {
    // Longest common factor = longest common substring (same as Problem08)
    public static String lcf(String s1, String s2) {
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
        System.out.println(lcf("xabcdy", "zabcdw")); // abcd
    }
}
