import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem42_ForkJoinParallelMergeSort {
    /**
     * Problem: ForkJoin Parallel Merge Sort
     * Parallel merge sort using ForkJoinPool.
     * Time: O(n log n) work, O(log n) span | Space: O(n)
     * Production Analogy: Parallel data processing in Spark/MapReduce.
     */
    static class MergeSortTask extends RecursiveAction {
        private final int[] arr;
        private final int lo, hi;
        MergeSortTask(int[] arr, int lo, int hi) { this.arr = arr; this.lo = lo; this.hi = hi; }

        protected void compute() {
            if (hi - lo <= 1) return;
            int mid = (lo + hi) / 2;
            MergeSortTask left = new MergeSortTask(arr, lo, mid);
            MergeSortTask right = new MergeSortTask(arr, mid, hi);
            invokeAll(left, right);
            merge(lo, mid, hi);
        }

        private void merge(int lo, int mid, int hi) {
            int[] temp = Arrays.copyOfRange(arr, lo, hi);
            int i = 0, j = mid - lo, k = lo;
            while (i < mid - lo && j < hi - lo) arr[k++] = temp[i] <= temp[j] ? temp[i++] : temp[j++];
            while (i < mid - lo) arr[k++] = temp[i++];
            while (j < hi - lo) arr[k++] = temp[j++];
        }
    }

    public static void main(String[] args) {
        int[] arr = {5, 3, 8, 1, 9, 2, 7, 4, 6};
        ForkJoinPool pool = new ForkJoinPool();
        pool.invoke(new MergeSortTask(arr, 0, arr.length));
        System.out.println("Sorted: " + Arrays.toString(arr));
    }
}
