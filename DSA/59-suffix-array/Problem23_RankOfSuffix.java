import java.util.*;

public class Problem23_RankOfSuffix {
    public static int[] computeRanks(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++) sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        int[] rank = new int[n];
        for (int i = 0; i < n; i++) rank[sa[i]] = i;
        return rank;
    }

    public static void main(String[] args) {
        String s = "banana";
        int[] rank = computeRanks(s);
        for (int i = 0; i < s.length(); i++)
            System.out.println("Suffix \"" + s.substring(i) + "\" has rank " + rank[i]);
    }
}
