import java.util.*;

/**
 * Problem 18: Quick Sort
 * 
 * D&C Approach:
 * - DIVIDE: Partition array around pivot (elements < pivot go left, > go right)
 * - CONQUER: Recursively sort left and right partitions
 * - COMBINE: No combine needed - partitioning places pivot in final position
 * 
 * Recurrence: T(n) = 2T(n/2) + O(n) average, T(n) = T(n-1) + O(n) worst
 * Time: O(n log n) average, O(n^2) worst. Space: O(log n) average
 * 
 * Production Analogy:
 * - C's qsort, Java's Arrays.sort for primitives (dual-pivot quicksort)
 * - In-place sorting when memory is constrained (no O(n) aux space)
 * - Introsort: quicksort with fallback to heapsort on bad partitions
 */
public class Problem18_QuickSort {

    private static Random rand = new Random();

    public static void quickSort(int[] arr, int lo, int hi) {
        if (lo >= hi) return;
        int pivot = partition(arr, lo, hi);
        quickSort(arr, lo, pivot - 1);
        quickSort(arr, pivot + 1, hi);
    }

    private static int partition(int[] arr, int lo, int hi) {
        // Randomized pivot
        int pivotIdx = lo + rand.nextInt(hi - lo + 1);
        int pivotVal = arr[pivotIdx];
        swap(arr, pivotIdx, hi);
        int store = lo;
        for (int i = lo; i < hi; i++) {
            if (arr[i] < pivotVal) { swap(arr, i, store); store++; }
        }
        swap(arr, store, hi);
        return store;
    }

    private static void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        int[] a1 = {10,7,8,9,1,5};
        quickSort(a1, 0, a1.length-1);
        System.out.println(Arrays.toString(a1));

        int[] a2 = {5,4,3,2,1};
        quickSort(a2, 0, a2.length-1);
        System.out.println(Arrays.toString(a2));

        int[] a3 = {1};
        quickSort(a3, 0, 0);
        System.out.println(Arrays.toString(a3));

        int[] a4 = {3,3,3,3};
        quickSort(a4, 0, a4.length-1);
        System.out.println(Arrays.toString(a4));
    }
}
