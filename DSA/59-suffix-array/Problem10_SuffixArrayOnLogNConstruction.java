import java.util.*;

public class Problem10_SuffixArrayOnLogNConstruction {
    // O(n log n) suffix array using doubling
    public static int[] buildSA(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        int[] rank = new int[n], tmp = new int[n];
        for (int i = 0; i < n; i++) { sa[i] = i; rank[i] = s.charAt(i); }
        for (int gap = 1; gap < n; gap *= 2) {
            final int g = gap;
            final int[] r = rank.clone();
            Comparator<Integer> cmp = (a, b) -> {
                if (r[a] != r[b]) return r[a] - r[b];
                int ra = a+g < n ? r[a+g] : -1, rb = b+g < n ? r[b+g] : -1;
                return ra - rb;
            };
            Arrays.sort(sa, cmp);
            tmp[sa[0]] = 0;
            for (int i = 1; i < n; i++) tmp[sa[i]] = tmp[sa[i-1]] + (cmp.compare(sa[i], sa[i-1]) != 0 ? 1 : 0);
            System.arraycopy(tmp, 0, rank, 0, n);
            if (rank[sa[n-1]] == n-1) break;
        }
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static void main(String[] args) {
        String s = "banana";
        int[] sa = buildSA(s);
        System.out.println(Arrays.toString(sa));
        for (int i : sa) System.out.println(i + ": " + s.substring(i));
    }
}
