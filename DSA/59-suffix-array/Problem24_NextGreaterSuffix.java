import java.util.*;

public class Problem24_NextGreaterSuffix {
    // For each suffix, find next lexicographically greater suffix
    public static int[] nextGreater(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n]; for(int i=0;i<n;i++) sa[i]=i;
        Arrays.sort(sa,(a,b)->s.substring(a).compareTo(s.substring(b)));
        int[] rank = new int[n]; for(int i=0;i<n;i++) rank[sa[i]]=i;
        int[] result = new int[n];
        for (int i = 0; i < n; i++) result[i] = rank[i]+1 < n ? sa[rank[i]+1] : -1;
        return result;
    }

    public static void main(String[] args) {
        String s = "banana";
        int[] ng = nextGreater(s);
        for (int i = 0; i < s.length(); i++)
            System.out.println(s.substring(i) + " -> next greater: " + (ng[i]>=0 ? s.substring(ng[i]) : "NONE"));
    }
}
