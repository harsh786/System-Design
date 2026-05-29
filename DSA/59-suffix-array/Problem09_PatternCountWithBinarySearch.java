import java.util.*;

public class Problem09_PatternCountWithBinarySearch {
    // Count occurrences of pattern using SA + binary search for range
    static int[] buildSA(String s) {
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        Arrays.sort(sa, (a, b) -> s.substring(a).compareTo(s.substring(b)));
        return Arrays.stream(sa).mapToInt(i->i).toArray();
    }

    public static int countOccurrences(String text, String pattern) {
        int[] sa = buildSA(text);
        int lo = lowerBound(text, sa, pattern);
        int hi = upperBound(text, sa, pattern);
        return hi - lo;
    }

    static int lowerBound(String text, int[] sa, String p) {
        int lo = 0, hi = sa.length;
        while (lo < hi) {
            int mid = (lo+hi)/2;
            String sub = text.substring(sa[mid], Math.min(sa[mid]+p.length(), text.length()));
            if (sub.compareTo(p) < 0) lo = mid+1; else hi = mid;
        }
        return lo;
    }

    static int upperBound(String text, int[] sa, String p) {
        int lo = 0, hi = sa.length;
        while (lo < hi) {
            int mid = (lo+hi)/2;
            String sub = text.substring(sa[mid], Math.min(sa[mid]+p.length(), text.length()));
            if (sub.compareTo(p) <= 0) lo = mid+1; else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(countOccurrences("banana", "an")); // 2
        System.out.println(countOccurrences("abababab", "ab")); // 4
    }
}
