import java.util.*;

/**
 * Problem 22: Sort an Array (Quick Sort)
 * 
 * Implement quicksort with randomized pivot to avoid worst case.
 * 
 * Approach: Pick random pivot, partition, recurse on halves.
 * Time Complexity: O(n log n) average, O(n²) worst
 * Space Complexity: O(log n) average stack space
 * Stability: Not stable
 * 
 * Production Analogy: Divide-and-conquer work distribution in parallel processing systems.
 * QuickSort's cache-friendly access pattern makes it preferred for in-memory sorting.
 */
public class Problem22_SortArrayQuickSort {
    
    private Random rand = new Random();
    
    public int[] sortArray(int[] nums) {
        quickSort(nums, 0, nums.length - 1);
        return nums;
    }
    
    private void quickSort(int[] nums, int lo, int hi) {
        if (lo >= hi) return;
        int pivotIdx = partition(nums, lo, hi);
        quickSort(nums, lo, pivotIdx - 1);
        quickSort(nums, pivotIdx + 1, hi);
    }
    
    private int partition(int[] nums, int lo, int hi) {
        int randIdx = lo + rand.nextInt(hi - lo + 1);
        swap(nums, randIdx, hi);
        int pivot = nums[hi], i = lo;
        for (int j = lo; j < hi; j++) {
            if (nums[j] < pivot) swap(nums, i++, j);
        }
        swap(nums, i, hi);
        return i;
    }
    
    private void swap(int[] a, int i, int j) {
        int t = a[i]; a[i] = a[j]; a[j] = t;
    }
    
    public static void main(String[] args) {
        Problem22_SortArrayQuickSort sol = new Problem22_SortArrayQuickSort();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortArray(new int[]{5,2,3,1}))); // [1,2,3,5]
        System.out.println("Test 2: " + Arrays.toString(sol.sortArray(new int[]{5,1,1,2,0,0}))); // [0,0,1,1,2,5]
        System.out.println("Test 3: " + Arrays.toString(sol.sortArray(new int[]{1}))); // [1]
        System.out.println("Test 4: " + Arrays.toString(sol.sortArray(new int[]{3,3,3,3,3}))); // [3,3,3,3,3]
    }
}
