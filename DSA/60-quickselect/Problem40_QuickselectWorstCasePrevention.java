import java.util.*;

public class Problem40_QuickselectWorstCasePrevention {
    /*
     * Quickselect with worst-case prevention using median-of-3 pivot
     */
    public int quickselect(int[] arr, int k) {
        int[] a = arr.clone();
        return select(a, 0, a.length - 1, k);
    }

    private int select(int[] a, int lo, int hi, int k) {
        if (lo == hi) return a[lo];
        int pi = medianOfThree(a, lo, hi);
        swap(a, pi, hi);
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) if (a[i] < pivot) swap(a, s++, i);
        swap(a, s, hi);
        if (s == k) return a[s];
        return s < k ? select(a, s + 1, hi, k) : select(a, lo, s - 1, k);
    }

    private int medianOfThree(int[] a, int lo, int hi) {
        int mid = lo + (hi - lo) / 2;
        if (a[lo] > a[mid]) swap(a, lo, mid);
        if (a[lo] > a[hi]) swap(a, lo, hi);
        if (a[mid] > a[hi]) swap(a, mid, hi);
        return mid;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem40_QuickselectWorstCasePrevention sol = new Problem40_QuickselectWorstCasePrevention();
        int[] arr = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}; // sorted - worst case for naive
        System.out.println(sol.quickselect(arr, 4)); // 5
    }
}
