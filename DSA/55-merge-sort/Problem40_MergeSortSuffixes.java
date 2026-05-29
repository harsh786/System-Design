import java.util.*;

public class Problem40_MergeSortSuffixes {
    // Build suffix array using merge sort
    static int[] buildSuffixArray(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        int[] result = new int[n];
        for (int i = 0; i < n; i++) result[i] = sa[i];
        return result;
    }
    
    public static void main(String[] args) {
        String s = "banana";
        int[] sa = buildSuffixArray(s);
        System.out.println(Arrays.toString(sa)); // [5,3,1,0,4,2]
        for (int i : sa) System.out.println(s.substring(i));
    }
}
