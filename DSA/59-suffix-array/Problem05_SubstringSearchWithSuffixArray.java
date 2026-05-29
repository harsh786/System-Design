import java.util.*;

public class Problem05_SubstringSearchWithSuffixArray {
    static int[] buildSA(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    // Binary search for pattern in suffix array
    public static int search(String text, int[] sa, String pattern) {
        int lo = 0, hi = sa.length - 1;
        while (lo <= hi) {
            int mid = (lo + hi) / 2;
            String suffix = text.substring(sa[mid], Math.min(sa[mid] + pattern.length(), text.length()));
            int cmp = suffix.compareTo(pattern);
            if (cmp == 0) return sa[mid];
            if (cmp < 0) lo = mid + 1; else hi = mid - 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        String text = "banana";
        int[] sa = buildSA(text);
        System.out.println("Found 'ana' at: " + search(text, sa, "ana")); // 1 or 3
        System.out.println("Found 'xyz' at: " + search(text, sa, "xyz")); // -1
    }
}
