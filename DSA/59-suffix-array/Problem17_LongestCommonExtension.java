import java.util.*;

public class Problem17_LongestCommonExtension {
    // LCE queries using SA + LCP + sparse table for RMQ
    int[] sa, rank, lcp;
    int[][] sparse;
    String s;

    public Problem17_LongestCommonExtension(String s) {
        this.s = s; int n = s.length();
        Integer[] saI = new Integer[n];
        for (int i = 0; i < n; i++) saI[i] = i;
        Arrays.sort(saI, (a,b)->s.substring(a).compareTo(s.substring(b)));
        sa = Arrays.stream(saI).mapToInt(i->i).toArray();
        rank = new int[n]; for (int i = 0; i < n; i++) rank[sa[i]] = i;
        // Kasai
        lcp = new int[n]; int h = 0;
        for (int i = 0; i < n; i++) {
            if (rank[i] > 0) {
                int j = sa[rank[i]-1];
                while (i+h<n && j+h<n && s.charAt(i+h)==s.charAt(j+h)) h++;
                lcp[rank[i]] = h; if (h>0) h--;
            } else h = 0;
        }
        // Build sparse table
        int log = (int)(Math.log(n)/Math.log(2)) + 1;
        sparse = new int[log+1][n];
        sparse[0] = lcp.clone();
        for (int k = 1; k <= log; k++)
            for (int i = 0; i + (1<<k) <= n; i++)
                sparse[k][i] = Math.min(sparse[k-1][i], sparse[k-1][i+(1<<(k-1))]);
    }

    public int query(int i, int j) {
        if (i == j) return s.length() - i;
        int l = Math.min(rank[i], rank[j]) + 1, r = Math.max(rank[i], rank[j]);
        int k = (int)(Math.log(r-l+1)/Math.log(2));
        return Math.min(sparse[k][l], sparse[k][r-(1<<k)+1]);
    }

    public static void main(String[] args) {
        Problem17_LongestCommonExtension lce = new Problem17_LongestCommonExtension("banana");
        System.out.println(lce.query(1, 3)); // LCE(1,3) = "ana" common prefix length = 3
        System.out.println(lce.query(0, 2)); // LCE(0,2) = 0 (b vs n)
    }
}
