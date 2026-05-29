import java.util.*;

/**
 * Problem 40: Sort an Array (LeetCode 912)
 * Implementing multiple D&C sorting strategies.
 * 
 * Approaches compared:
 * 1. Merge Sort: O(n log n) guaranteed, stable, O(n) space
 * 2. Quick Sort: O(n log n) avg, in-place, not stable
 * 3. Heap Sort: O(n log n) guaranteed, in-place, not stable
 * 
 * Production Analogy:
 * - Java Arrays.sort: Dual-pivot Quicksort for primitives, TimSort for objects
 * - Python: TimSort (hybrid merge sort + insertion sort)
 * - C++ std::sort: Introsort (quicksort + heapsort + insertion sort)
 */
public class Problem40_SortAnArray {

    // 3-way partitioning quicksort (handles duplicates well)
    public static int[] sortArray(int[] nums) {
        shuffle(nums); // Randomize to avoid worst case
        quickSort3Way(nums, 0, nums.length - 1);
        return nums;
    }

    private static void quickSort3Way(int[] arr, int lo, int hi) {
        if (lo >= hi) return;
        int lt = lo, gt = hi, i = lo + 1;
        int pivot = arr[lo];
        while (i <= gt) {
            if (arr[i] < pivot) swap(arr, lt++, i++);
            else if (arr[i] > pivot) swap(arr, i, gt--);
            else i++;
        }
        quickSort3Way(arr, lo, lt - 1);
        quickSort3Way(arr, gt + 1, hi);
    }

    private static void shuffle(int[] arr) {
        Random rand = new Random();
        for (int i = arr.length - 1; i > 0; i--) {
            swap(arr, i, rand.nextInt(i + 1));
        }
    }

    private static void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortArray(new int[]{5,2,3,1})));      // [1,2,3,5]
        System.out.println(Arrays.toString(sortArray(new int[]{5,1,1,2,0,0})));  // [0,0,1,1,2,5]
        System.out.println(Arrays.toString(sortArray(new int[]{1})));            // [1]
        System.out.println(Arrays.toString(sortArray(new int[]{2,2,2,2})));      // [2,2,2,2]
        System.out.println(Arrays.toString(sortArray(new int[]{-1,0,1,-2,2})));  // [-2,-1,0,1,2]
    }
}
