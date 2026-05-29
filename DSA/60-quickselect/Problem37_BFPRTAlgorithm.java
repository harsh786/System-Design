import java.util.*;

public class Problem37_BFPRTAlgorithm {
    /* BFPRT (Blum-Floyd-Pratt-Rivest-Tarjan) - Median of Medians guaranteed O(n) */
    public int bfprt(int[] arr, int k) {
        return bfprt(arr.clone(), 0, arr.length - 1, k);
    }

    private int bfprt(int[] arr, int lo, int hi, int k) {
        if (lo == hi) return arr[lo];
        int pivot = getMedianOfMedians(arr, lo, hi);
        int pi = partition(arr, lo, hi, pivot);
        if (pi == k) return arr[pi];
        return pi < k ? bfprt(arr, pi + 1, hi, k) : bfprt(arr, lo, pi - 1, k);
    }

    private int getMedianOfMedians(int[] arr, int lo, int hi) {
        int n = hi - lo + 1;
        if (n <= 5) { Arrays.sort(arr, lo, hi + 1); return arr[lo + n / 2]; }
        int[] medians = new int[(n + 4) / 5];
        for (int i = 0; i < medians.length; i++) {
            int start = lo + i * 5, end = Math.min(start + 4, hi);
            Arrays.sort(arr, start, end + 1);
            medians[i] = arr[start + (end - start) / 2];
        }
        return bfprt(medians, 0, medians.length - 1, medians.length / 2);
    }

    private int partition(int[] arr, int lo, int hi, int pivot) {
        for (int i = lo; i <= hi; i++) if (arr[i] == pivot) { swap(arr, i, hi); break; }
        int s = lo;
        for (int i = lo; i < hi; i++) if (arr[i] < pivot) swap(arr, s++, i);
        swap(arr, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem37_BFPRTAlgorithm sol = new Problem37_BFPRTAlgorithm();
        System.out.println(sol.bfprt(new int[]{3,2,1,5,6,4}, 2)); // 3
    }
}
