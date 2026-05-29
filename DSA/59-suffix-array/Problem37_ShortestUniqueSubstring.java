import java.util.*;

public class Problem37_ShortestUniqueSubstring {
    // Find shortest substring that appears exactly once
    public static String shortestUnique(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++)sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        int[] lcp = new int[n];
        // Build LCP
        int[] rank = new int[n]; for(int i=0;i<n;i++)rank[sa[i]]=i;
        int h=0; for(int i=0;i<n;i++){if(rank[i]>0){int j=sa[rank[i]-1];while(i+h<n&&j+h<n&&s.charAt(i+h)==s.charAt(j+h))h++;lcp[rank[i]]=h;if(h>0)h--;}else h=0;}

        String best = s;
        for (int i = 0; i < n; i++) {
            int maxLcp = Math.max(lcp[i], i+1<n ? lcp[i+1] : 0);
            int uniqueLen = maxLcp + 1;
            if (sa[i]+uniqueLen <= n && uniqueLen < best.length())
                best = s.substring(sa[i], sa[i]+uniqueLen);
        }
        return best;
    }

    public static void main(String[] args) {
        System.out.println(shortestUnique("aababaa")); // shortest unique substring
        System.out.println(shortestUnique("abcabc")); // unique short substring
    }
}
