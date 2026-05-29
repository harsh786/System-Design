import java.util.*;

public class Problem41_EnhancedSuffixArray {
    // Enhanced SA = SA + LCP + child table for O(m) pattern matching
    int[] sa, lcp, rank;
    String s;

    public Problem41_EnhancedSuffixArray(String s) {
        this.s = s; int n = s.length();
        Integer[] saI = new Integer[n]; for(int i=0;i<n;i++)saI[i]=i;
        Arrays.sort(saI,(a,b)->s.substring(a).compareTo(s.substring(b)));
        sa = Arrays.stream(saI).mapToInt(i->i).toArray();
        rank = new int[n]; for(int i=0;i<n;i++) rank[sa[i]]=i;
        // Kasai LCP
        lcp = new int[n]; int h=0;
        for(int i=0;i<n;i++){if(rank[i]>0){int j=sa[rank[i]-1];while(i+h<n&&j+h<n&&s.charAt(i+h)==s.charAt(j+h))h++;lcp[rank[i]]=h;if(h>0)h--;}else h=0;}
    }

    public int countDistinctSubstrings() {
        long total = (long)s.length()*(s.length()+1)/2;
        for (int l : lcp) total -= l;
        return (int) total;
    }

    public static void main(String[] args) {
        Problem41_EnhancedSuffixArray esa = new Problem41_EnhancedSuffixArray("banana");
        System.out.println("Distinct substrings: " + esa.countDistinctSubstrings());
        System.out.println("SA: " + Arrays.toString(esa.sa));
        System.out.println("LCP: " + Arrays.toString(esa.lcp));
    }
}
