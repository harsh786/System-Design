import java.util.*;

public class Problem15_SuffixArrayDoublingAlgorithm {
    // Detailed O(n log^2 n) implementation
    public static int[] buildSA(String s) {
        int n = s.length();
        Integer[] order = new Integer[n];
        int[] rank = new int[n], tmp = new int[n];
        for (int i = 0; i < n; i++) { order[i] = i; rank[i] = s.charAt(i); }

        for (int gap = 1; gap < n; gap <<= 1) {
            final int g = gap; final int[] r = rank.clone();
            Arrays.sort(order, (a, b) -> {
                if (r[a] != r[b]) return r[a] - r[b];
                int ra = a+g < n ? r[a+g] : -1, rb = b+g < n ? r[b+g] : -1;
                return ra - rb;
            });
            tmp[order[0]] = 0;
            for (int i = 1; i < n; i++) {
                tmp[order[i]] = tmp[order[i-1]];
                if (r[order[i]] != r[order[i-1]] ||
                    (order[i]+g<n?r[order[i]+g]:-1) != (order[i-1]+g<n?r[order[i-1]+g]:-1))
                    tmp[order[i]]++;
            }
            System.arraycopy(tmp, 0, rank, 0, n);
        }
        return Arrays.stream(order).mapToInt(i->i).toArray();
    }

    public static void main(String[] args) {
        String s = "mississippi";
        int[] sa = buildSA(s);
        for (int i : sa) System.out.println(i + ": " + s.substring(i));
    }
}
