import java.util.*;

public class Problem45_QuickselectLoadBalancing {
    /* Find the median server load to balance around */
    public int findBalancePoint(int[] loads) {
        int n = loads.length;
        int[] a = loads.clone();
        return quickselect(a, 0, n - 1, n / 2);
    }

    private int quickselect(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = partition(a, lo, hi);
        if (pi == k) return a[pi];
        return pi < k ? quickselect(a, pi + 1, hi, k) : quickselect(a, lo, pi - 1, k);
    }

    private int partition(int[] a, int lo, int hi) {
        int pivot = a[lo + (hi - lo) / 2]; swap(a, lo + (hi - lo) / 2, hi);
        int s = lo;
        for (int i = lo; i < hi; i++) if (a[i] < pivot) swap(a, s++, i);
        swap(a, s, hi); return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem45_QuickselectLoadBalancing sol = new Problem45_QuickselectLoadBalancing();
        int[] loads = {100, 50, 200, 75, 150, 25, 300};
        System.out.println("Balance point (median load): " + sol.findBalancePoint(loads));
    }
}
