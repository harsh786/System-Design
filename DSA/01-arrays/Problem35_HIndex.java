import java.util.*;

/**
 * Problem 35: H-Index
 * Find h such that h papers have at least h citations each.
 * 
 * Production Analogy: Like finding service tier threshold - how many services
 * have at least T requests (for auto-scaling tier classification).
 * 
 * O(n) time with counting sort, O(n log n) with regular sort
 */
public class Problem35_HIndex {

    public static int hIndex(int[] citations) {
        int n = citations.length;
        int[] count = new int[n + 1];
        for (int c : citations) count[Math.min(c, n)]++;
        int total = 0;
        for (int i = n; i >= 0; i--) {
            total += count[i];
            if (total >= i) return i;
        }
        return 0;
    }

    public static void main(String[] args) {
        System.out.println(hIndex(new int[]{3,0,6,1,5})); // 3
        System.out.println(hIndex(new int[]{1,3,1}));      // 1
        System.out.println(hIndex(new int[]{0}));           // 0
    }
}
