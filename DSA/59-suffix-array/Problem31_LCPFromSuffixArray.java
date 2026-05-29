import java.util.*;

public class Problem31_LCPFromSuffixArray {
    // Kasai's algorithm
    public static int[] buildLCP(String s, int[] sa) {
        int n = s.length();
        int[] rank = new int[n], lcp = new int[n];
        for (int i = 0; i < n; i++) rank[sa[i]] = i;
        int h = 0;
        for (int i = 0; i < n; i++) {
            if (rank[i] > 0) {
                int j = sa[rank[i]-1];
                while (i+h<n && j+h<n && s.charAt(i+h)==s.charAt(j+h)) h++;
                lcp[rank[i]] = h; if(h>0) h--;
            } else h=0;
        }
        return lcp;
    }

    public static void main(String[] args) {
        String s = "abcabcabc";
        int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        int[] saArr = Arrays.stream(sa).mapToInt(i->i).toArray();
        int[] lcp = buildLCP(s, saArr);
        System.out.println("LCP: " + Arrays.toString(lcp));
    }
}
