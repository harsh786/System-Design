import java.util.*;

public class Problem43_QuickselectPercentile {
    public double percentile(int[] arr, double p) {
        int n = arr.length;
        double rank = p / 100.0 * (n - 1);
        int lo = (int) Math.floor(rank), hi = (int) Math.ceil(rank);
        int[] a = arr.clone();
        int loVal = quickselect(a, 0, n - 1, lo);
        if (lo == hi) return loVal;
        a = arr.clone();
        int hiVal = quickselect(a, 0, n - 1, hi);
        return loVal + (rank - lo) * (hiVal - loVal);
    }

    private int quickselect(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = partition(a, lo, hi);
        if (pi == k) return a[pi];
        return pi < k ? quickselect(a, pi + 1, hi, k) : quickselect(a, lo, pi - 1, k);
    }

    private int partition(int[] a, int lo, int hi) {
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) if (a[i] < pivot) { int t = a[s]; a[s] = a[i]; a[i] = t; s++; }
        int t = a[s]; a[s] = a[hi]; a[hi] = t;
        return s;
    }

    public static void main(String[] args) {
        Problem43_QuickselectPercentile sol = new Problem43_QuickselectPercentile();
        System.out.println("P50: " + sol.percentile(new int[]{15, 20, 35, 40, 50}, 50));
        System.out.println("P90: " + sol.percentile(new int[]{15, 20, 35, 40, 50}, 90));
    }
}
