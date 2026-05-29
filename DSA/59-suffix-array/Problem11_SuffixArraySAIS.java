import java.util.*;

public class Problem11_SuffixArraySAIS {
    // SA-IS concept: linear time suffix array construction
    // Simplified explanation with naive implementation
    // SA-IS classifies suffixes as S-type or L-type, identifies LMS suffixes,
    // recursively sorts LMS suffixes, then induces full order

    public static int[] buildSANaive(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static void main(String[] args) {
        String s = "mmiissiissiippii";
        int[] sa = buildSANaive(s);
        System.out.println("SA-IS concept demo (using naive sort):");
        for (int i : sa) System.out.println(i + ": " + s.substring(i));
    }
}
