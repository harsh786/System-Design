import java.util.Arrays;

/**
 * Problem 46: Count Inversions with Merge Sort (detailed variant)
 * Shows step-by-step how inversions are counted during merge phase.
 * 
 * D&C Approach:
 * - DIVIDE: Split array into halves
 * - CONQUER: Count inversions within each half (split inversions)
 * - COMBINE: Count cross-inversions during merge
 *   When arr[j] < arr[i] (right before left), inversions += (mid - i + 1)
 *   because all elements from i to mid are greater than arr[j]
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Measuring Kendall tau distance between two rankings
 * - Evaluating how "unsorted" a nearly-sorted dataset is (adaptive sorting)
 * - Collaborative filtering: comparing user preference orderings
 */
public class Problem46_CountInversionsWithMergeSort {

    static long inversions;

    public static long countInversions(int[] arr) {
        inversions = 0;
        int[] temp = Arrays.copyOf(arr, arr.length);
        mergeSort(temp, 0, temp.length - 1);
        return inversions;
    }

    private static void mergeSort(int[] arr, int lo, int hi) {
        if (lo >= hi) return;
        int mid = lo + (hi - lo) / 2;
        mergeSort(arr, lo, mid);
        mergeSort(arr, mid + 1, hi);
        merge(arr, lo, mid, hi);
    }

    private static void merge(int[] arr, int lo, int mid, int hi) {
        int[] left = Arrays.copyOfRange(arr, lo, mid + 1);
        int[] right = Arrays.copyOfRange(arr, mid + 1, hi + 1);
        int i = 0, j = 0, k = lo;
        while (i < left.length && j < right.length) {
            if (left[i] <= right[j]) {
                arr[k++] = left[i++];
            } else {
                // All remaining elements in left are inversions with right[j]
                inversions += (left.length - i);
                arr[k++] = right[j++];
            }
        }
        while (i < left.length) arr[k++] = left[i++];
        while (j < right.length) arr[k++] = right[j++];
    }

    public static void main(String[] args) {
        System.out.println(countInversions(new int[]{2, 4, 1, 3, 5})); // 3
        System.out.println(countInversions(new int[]{5, 4, 3, 2, 1})); // 10
        System.out.println(countInversions(new int[]{1, 2, 3, 4, 5})); // 0
        System.out.println(countInversions(new int[]{1, 20, 6, 4, 5})); // 5
        System.out.println(countInversions(new int[]{8, 4, 2, 1})); // 6
        System.out.println(countInversions(new int[]{3, 1, 2})); // 2
    }
}
