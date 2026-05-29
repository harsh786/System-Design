import java.util.*;

public class Problem30_SuffixArrayConstructionNLogSquared {
    // O(n log^2 n) with sorting by pairs of ranks
    public static int[] buildSA(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        int[] rank = new int[n], tmp = new int[n];
        for (int i = 0; i < n; i++) { sa[i] = i; rank[i] = s.charAt(i); }
        for (int gap = 1; gap < n; gap <<= 1) {
            final int g = gap; final int[] r = rank.clone();
            Arrays.sort(sa, (a, b) -> r[a]!=r[b] ? r[a]-r[b] : (a+g<n?r[a+g]:-1) - (b+g<n?r[b+g]:-1));
            tmp[sa[0]] = 0;
            for (int i = 1; i < n; i++) {
                tmp[sa[i]] = tmp[sa[i-1]];
                if (r[sa[i]]!=r[sa[i-1]] || (sa[i]+g<n?r[sa[i]+g]:-1)!=(sa[i-1]+g<n?r[sa[i-1]+g]:-1)) tmp[sa[i]]++;
            }
            System.arraycopy(tmp, 0, rank, 0, n);
        }
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static void main(String[] args) {
        String s = "mississippi";
        int[] sa = buildSA(s);
        for (int i : sa) System.out.println(i + ": " + s.substring(i));
    }
}
