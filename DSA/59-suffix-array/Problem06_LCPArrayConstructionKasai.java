import java.util.*;

public class Problem06_LCPArrayConstructionKasai {
    // Kasai's algorithm: O(n) LCP array from suffix array
    public static int[] kasai(String s, int[] sa) {
        int n = s.length();
        int[] rank = new int[n], lcp = new int[n];
        for (int i = 0; i < n; i++) rank[sa[i]] = i;
        int h = 0;
        for (int i = 0; i < n; i++) {
            if (rank[i] > 0) {
                int j = sa[rank[i] - 1];
                while (i+h < n && j+h < n && s.charAt(i+h) == s.charAt(j+h)) h++;
                lcp[rank[i]] = h;
                if (h > 0) h--;
            } else h = 0;
        }
        return lcp;
    }

    public static void main(String[] args) {
        String s = "banana";
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        int[] saArr = Arrays.stream(sa).mapToInt(i->i).toArray();
        int[] lcp = kasai(s, saArr);
        System.out.println("SA:  " + Arrays.toString(saArr));
        System.out.println("LCP: " + Arrays.toString(lcp));
        for (int i = 0; i < n; i++) System.out.println(saArr[i] + ": " + s.substring(saArr[i]) + " (lcp=" + lcp[i] + ")");
    }
}
