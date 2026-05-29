import java.util.*;

public class Problem35_PartialSortTopK {
    /* Partial sort: find top-k elements in sorted order using quickselect + sort */
    public int[] topK(int[] arr, int k) {
        int n = arr.length;
        quickselect(arr, 0, n - 1, n - k);
        int[] top = Arrays.copyOfRange(arr, n - k, n);
        Arrays.sort(top);
        return top;
    }

    private void quickselect(int[] a, int lo, int hi, int k) {
        if (lo >= hi) return;
        int pi = partition(a, lo, hi);
        if (pi == k) return;
        else if (pi < k) quickselect(a, pi + 1, hi, k);
        else quickselect(a, lo, pi - 1, k);
    }

    private int partition(int[] a, int lo, int hi) {
        int pivot = a[hi], s = lo;
        for (int i = lo; i < hi; i++) if (a[i] < pivot) { int t = a[s]; a[s] = a[i]; a[i] = t; s++; }
        int t = a[s]; a[s] = a[hi]; a[hi] = t;
        return s;
    }

    public static void main(String[] args) {
        Problem35_PartialSortTopK sol = new Problem35_PartialSortTopK();
        System.out.println(Arrays.toString(sol.topK(new int[]{3,1,4,1,5,9,2,6}, 3)));
    }
}
