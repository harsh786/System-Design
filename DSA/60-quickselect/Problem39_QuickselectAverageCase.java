import java.util.*;

public class Problem39_QuickselectAverageCase {
    /*
     * Quickselect Average Case Analysis Demo
     * Demonstrates that average comparisons ~ 2n + o(n) for finding median
     */
    private int comparisons;

    public int quickselectCounting(int[] arr, int k) {
        comparisons = 0;
        int[] a = arr.clone();
        return select(a, 0, a.length - 1, k);
    }

    private int select(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = lo + new Random().nextInt(hi - lo + 1);
        swap(a, pi, hi);
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) { comparisons++; if (a[i] < pivot) swap(a, s++, i); }
        swap(a, s, hi);
        if (s == k) return a[s];
        return s < k ? select(a, s + 1, hi, k) : select(a, lo, s - 1, k);
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem39_QuickselectAverageCase sol = new Problem39_QuickselectAverageCase();
        int n = 10000;
        int[] arr = new int[n];
        Random r = new Random(42);
        for (int i = 0; i < n; i++) arr[i] = r.nextInt(100000);
        sol.quickselectCounting(arr, n / 2);
        System.out.println("n=" + n + " comparisons=" + sol.comparisons + " ratio=" + (double)sol.comparisons / n);
    }
}
