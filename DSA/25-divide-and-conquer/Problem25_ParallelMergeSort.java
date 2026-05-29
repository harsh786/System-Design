import java.util.*;
import java.util.concurrent.*;

/**
 * Problem 25: Parallel Merge Sort
 * 
 * D&C Approach with parallelism:
 * - DIVIDE: Split array into halves
 * - CONQUER: Sort each half in parallel (separate threads/tasks)
 * - COMBINE: Merge sorted halves (sequential or parallel merge)
 * 
 * Time: O(n log n / p + n) where p = number of processors
 * Space: O(n) + thread overhead
 * Span (critical path): O(n) due to sequential merge
 * 
 * Production Analogy:
 * - Java's parallelSort (ForkJoinPool based)
 * - MapReduce sort phase (each mapper sorts partition in parallel)
 * - GPU-based sorting (parallel prefix operations)
 */
public class Problem25_ParallelMergeSort {

    private static final int THRESHOLD = 1000; // Below this, use sequential sort

    static class MergeSortTask extends RecursiveAction {
        private int[] arr, temp;
        private int lo, hi;

        MergeSortTask(int[] arr, int[] temp, int lo, int hi) {
            this.arr = arr; this.temp = temp; this.lo = lo; this.hi = hi;
        }

        @Override
        protected void compute() {
            if (hi - lo <= THRESHOLD) {
                Arrays.sort(arr, lo, hi + 1);
                return;
            }
            int mid = lo + (hi - lo) / 2;
            MergeSortTask left = new MergeSortTask(arr, temp, lo, mid);
            MergeSortTask right = new MergeSortTask(arr, temp, mid + 1, hi);
            invokeAll(left, right); // Fork both tasks
            merge(arr, temp, lo, mid, hi);
        }
    }

    private static void merge(int[] arr, int[] temp, int lo, int mid, int hi) {
        System.arraycopy(arr, lo, temp, lo, hi - lo + 1);
        int i = lo, j = mid + 1, k = lo;
        while (i <= mid && j <= hi) {
            if (temp[i] <= temp[j]) arr[k++] = temp[i++];
            else arr[k++] = temp[j++];
        }
        while (i <= mid) arr[k++] = temp[i++];
    }

    public static void parallelMergeSort(int[] arr) {
        int[] temp = new int[arr.length];
        ForkJoinPool pool = ForkJoinPool.commonPool();
        pool.invoke(new MergeSortTask(arr, temp, 0, arr.length - 1));
    }

    public static void main(String[] args) {
        // Small test
        int[] arr1 = {5, 3, 8, 1, 9, 2, 7, 4, 6};
        parallelMergeSort(arr1);
        System.out.println(Arrays.toString(arr1));

        // Larger test
        Random rand = new Random(42);
        int[] arr2 = new int[10000];
        for (int i = 0; i < arr2.length; i++) arr2[i] = rand.nextInt(100000);
        parallelMergeSort(arr2);
        // Verify sorted
        boolean sorted = true;
        for (int i = 1; i < arr2.length; i++) if (arr2[i] < arr2[i-1]) { sorted = false; break; }
        System.out.println("Large array sorted: " + sorted);

        // Edge case
        int[] arr3 = {1};
        parallelMergeSort(arr3);
        System.out.println(Arrays.toString(arr3));
    }
}
