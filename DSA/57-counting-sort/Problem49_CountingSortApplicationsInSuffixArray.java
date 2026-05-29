import java.util.*;

public class Problem49_CountingSortApplicationsInSuffixArray {
    // Counting sort as subroutine in suffix array construction (radix sort step)
    public static int[] buildSuffixArray(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        // Simple O(n log^2 n) with counting sort for ranking
        int[] rank = new int[n], tmp = new int[n];
        for (int i = 0; i < n; i++) rank[i] = s.charAt(i);
        for (int gap = 1; gap < n; gap *= 2) {
            final int g = gap;
            final int[] r = rank;
            Arrays.sort(sa, (a, b) -> r[a] != r[b] ? r[a] - r[b] : 
                (a+g<n&&b+g<n ? r[a+g]-r[b+g] : (a+g>=n?-1:1)));
            tmp[sa[0]] = 0;
            for (int i = 1; i < n; i++) {
                tmp[sa[i]] = tmp[sa[i-1]];
                if (r[sa[i]] != r[sa[i-1]] || (sa[i]+g<n?r[sa[i]+g]:-1) != (sa[i-1]+g<n?r[sa[i-1]+g]:-1))
                    tmp[sa[i]]++;
            }
            System.arraycopy(tmp, 0, rank, 0, n);
        }
        int[] result = new int[n];
        for (int i = 0; i < n; i++) result[i] = sa[i];
        return result;
    }

    public static void main(String[] args) {
        String s = "banana";
        int[] sa = buildSuffixArray(s);
        System.out.println("Suffix Array: " + Arrays.toString(sa));
        for (int i : sa) System.out.println(i + ": " + s.substring(i));
    }
}
