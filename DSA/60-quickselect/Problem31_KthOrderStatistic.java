import java.util.*;

public class Problem31_KthOrderStatistic {
    public int kthOrderStatistic(int[] arr, int k) {
        return quickselect(arr, 0, arr.length - 1, k - 1);
    }

    private int quickselect(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = partition(a, lo, hi);
        if (pi == k) return a[pi];
        return pi < k ? quickselect(a, pi + 1, hi, k) : quickselect(a, lo, pi - 1, k);
    }

    private int partition(int[] a, int lo, int hi) {
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) if (a[i] <= pivot) { int t = a[s]; a[s] = a[i]; a[i] = t; s++; }
        int t = a[s]; a[s] = a[hi]; a[hi] = t;
        return s;
    }

    public static void main(String[] args) {
        Problem31_KthOrderStatistic sol = new Problem31_KthOrderStatistic();
        System.out.println(sol.kthOrderStatistic(new int[]{7, 10, 4, 3, 20, 15}, 4)); // 10
    }
}
