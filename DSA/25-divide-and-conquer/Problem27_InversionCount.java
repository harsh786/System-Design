import java.util.Arrays;

/**
 * Problem 27: Inversion Count
 * Count pairs (i,j) where i < j but arr[i] > arr[j]
 * 
 * D&C Approach (Modified Merge Sort):
 * - DIVIDE: Split array into halves
 * - CONQUER: Count inversions in each half
 * - COMBINE: During merge, when right element goes before left elements,
 *   all remaining left elements form inversions with it
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Measuring "disorder" in recommendation rankings (Kendall tau distance)
 * - Collaborative filtering similarity metrics
 * - Detecting how far a list is from sorted (useful in adaptive sort algorithms)
 */
public class Problem27_InversionCount {

    public static long countInversions(int[] arr) {
        int[] temp = new int[arr.length];
        return mergeSort(arr, temp, 0, arr.length - 1);
    }

    private static long mergeSort(int[] arr, int[] temp, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = lo + (hi - lo) / 2;
        long count = 0;
        count += mergeSort(arr, temp, lo, mid);
        count += mergeSort(arr, temp, mid + 1, hi);
        count += merge(arr, temp, lo, mid, hi);
        return count;
    }

    private static long merge(int[] arr, int[] temp, int lo, int mid, int hi) {
        int i = lo, j = mid + 1, k = lo;
        long inversions = 0;
        while (i <= mid && j <= hi) {
            if (arr[i] <= arr[j]) {
                temp[k++] = arr[i++];
            } else {
                inversions += (mid - i + 1); // All remaining left elements are inversions
                temp[k++] = arr[j++];
            }
        }
        while (i <= mid) temp[k++] = arr[i++];
        while (j <= hi) temp[k++] = arr[j++];
        System.arraycopy(temp, lo, arr, lo, hi - lo + 1);
        return inversions;
    }

    public static void main(String[] args) {
        System.out.println(countInversions(new int[]{2, 4, 1, 3, 5})); // 3
        System.out.println(countInversions(new int[]{5, 4, 3, 2, 1})); // 10
        System.out.println(countInversions(new int[]{1, 2, 3, 4, 5})); // 0
        System.out.println(countInversions(new int[]{1, 20, 6, 4, 5})); // 5
        System.out.println(countInversions(new int[]{1})); // 0
    }
}
