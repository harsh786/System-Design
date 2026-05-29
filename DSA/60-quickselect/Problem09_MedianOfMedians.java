import java.util.*;

public class Problem09_MedianOfMedians {
    /*
     * Median of Medians - deterministic O(n) selection algorithm
     * Guarantees O(n) worst case for kth smallest
     */
    public int select(int[] arr, int k) {
        return select(arr, 0, arr.length - 1, k);
    }

    private int select(int[] arr, int lo, int hi, int k) {
        if (lo == hi) return arr[lo];
        int pivot = medianOfMedians(arr, lo, hi);
        int pivotIdx = partitionAround(arr, lo, hi, pivot);
        if (k == pivotIdx) return arr[k];
        else if (k < pivotIdx) return select(arr, lo, pivotIdx - 1, k);
        else return select(arr, pivotIdx + 1, hi, k);
    }

    private int medianOfMedians(int[] arr, int lo, int hi) {
        int n = hi - lo + 1;
        if (n <= 5) {
            Arrays.sort(arr, lo, hi + 1);
            return arr[lo + n / 2];
        }
        int numGroups = (n + 4) / 5;
        int[] medians = new int[numGroups];
        for (int i = 0; i < numGroups; i++) {
            int groupStart = lo + i * 5;
            int groupEnd = Math.min(groupStart + 4, hi);
            Arrays.sort(arr, groupStart, groupEnd + 1);
            medians[i] = arr[groupStart + (groupEnd - groupStart) / 2];
        }
        return select(medians, 0, medians.length - 1, medians.length / 2);
    }

    private int partitionAround(int[] arr, int lo, int hi, int pivot) {
        int pivotIdx = lo;
        for (int i = lo; i <= hi; i++) { if (arr[i] == pivot) { pivotIdx = i; break; } }
        swap(arr, pivotIdx, hi);
        int s = lo;
        for (int i = lo; i < hi; i++) {
            if (arr[i] < pivot) { swap(arr, s++, i); }
        }
        swap(arr, s, hi);
        return s;
    }

    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        Problem09_MedianOfMedians sol = new Problem09_MedianOfMedians();
        int[] arr = {12, 3, 5, 7, 4, 19, 26};
        System.out.println(sol.select(arr, 3)); // 7 (0-indexed 3rd smallest)
    }
}
