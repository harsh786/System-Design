import java.util.*;

public class Problem29_SuffixArrayConstructionNaive {
    // O(n^2 log n) naive construction
    public static int[] buildSA(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static void main(String[] args) {
        String s = "banana";
        int[] sa = buildSA(s);
        System.out.println("Suffix Array (naive O(n^2 log n)):");
        for (int i : sa) System.out.println(i + ": " + s.substring(i));
    }
}
