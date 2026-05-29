import java.util.*;

public class Problem36_Introselect {
    /*
     * Introselect: hybrid of quickselect and median-of-medians
     * Falls back to median-of-medians after too many bad partitions
     */
    public int introselect(int[] arr, int k) {
        return introselect(arr, 0, arr.length - 1, k, 2 * (int)(Math.log(arr.length) / Math.log(2)));
    }

    private int introselect(int[] arr, int lo, int hi, int k, int maxDepth) {
        if (lo == hi) return arr[lo];
        if (maxDepth == 0) return medianOfMediansSelect(arr, lo, hi, k);
        int pi = randomPartition(arr, lo, hi);
        if (pi == k) return arr[pi];
        else if (pi < k) return introselect(arr, pi + 1, hi, k, maxDepth - 1);
        else return introselect(arr, lo, pi - 1, k, maxDepth - 1);
    }

    private int medianOfMediansSelect(int[] arr, int lo, int hi, int k) {
        if (hi - lo < 5) { Arrays.sort(arr, lo, hi + 1); return arr[k]; }
        for (int i = lo; i <= hi; i += 5) {
            int end = Math.min(i + 4, hi);
            Arrays.sort(arr, i, end + 1);
            swap(arr, lo + (i - lo) / 5, i + (end - i) / 2);
        }
        int numMedians = (hi - lo) / 5;
        int pivot = medianOfMediansSelect(arr, lo, lo + numMedians, lo + numMedians / 2);
        int pi = partitionAround(arr, lo, hi, pivot);
        if (pi == k) return arr[pi];
        else if (pi < k) return medianOfMediansSelect(arr, pi + 1, hi, k);
        else return medianOfMediansSelect(arr, lo, pi - 1, k);
    }

    private int partitionAround(int[] arr, int lo, int hi, int pivot) {
        for (int i = lo; i <= hi; i++) if (arr[i] == pivot) { swap(arr, i, hi); break; }
        int s = lo;
        for (int i = lo; i < hi; i++) if (arr[i] < pivot) swap(arr, s++, i);
        swap(arr, s, hi);
        return s;
    }

    private int randomPartition(int[] arr, int lo, int hi) {
        int pi = lo + new Random().nextInt(hi - lo + 1);
        swap(arr, pi, hi);
        int pivot = arr[hi], s = lo;
        for (int i = lo; i < hi; i++) if (arr[i] < pivot) swap(arr, s++, i);
        swap(arr, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem36_Introselect sol = new Problem36_Introselect();
        int[] arr = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5};
        System.out.println(sol.introselect(arr, 5)); // 4
    }
}
