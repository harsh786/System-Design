import java.util.*;

/**
 * Problem 21: Sort an Array (Merge Sort)
 * 
 * Implement merge sort.
 * 
 * Approach: Divide array in half, recursively sort, merge sorted halves.
 * Time Complexity: O(n log n) always
 * Space Complexity: O(n) for auxiliary array
 * Stability: Stable
 * 
 * Production Analogy: MapReduce paradigm - split data across nodes (map), sort locally,
 * merge results (reduce). Used in external sorting for databases.
 */
public class Problem21_SortArrayMergeSort {
    
    public int[] sortArray(int[] nums) {
        if (nums.length <= 1) return nums;
        mergeSort(nums, 0, nums.length - 1, new int[nums.length]);
        return nums;
    }
    
    private void mergeSort(int[] nums, int lo, int hi, int[] temp) {
        if (lo >= hi) return;
        int mid = lo + (hi - lo) / 2;
        mergeSort(nums, lo, mid, temp);
        mergeSort(nums, mid + 1, hi, temp);
        merge(nums, lo, mid, hi, temp);
    }
    
    private void merge(int[] nums, int lo, int mid, int hi, int[] temp) {
        System.arraycopy(nums, lo, temp, lo, hi - lo + 1);
        int i = lo, j = mid + 1, k = lo;
        while (i <= mid && j <= hi) {
            if (temp[i] <= temp[j]) nums[k++] = temp[i++];
            else nums[k++] = temp[j++];
        }
        while (i <= mid) nums[k++] = temp[i++];
    }
    
    public static void main(String[] args) {
        Problem21_SortArrayMergeSort sol = new Problem21_SortArrayMergeSort();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortArray(new int[]{5,2,3,1}))); // [1,2,3,5]
        System.out.println("Test 2: " + Arrays.toString(sol.sortArray(new int[]{5,1,1,2,0,0}))); // [0,0,1,1,2,5]
        System.out.println("Test 3: " + Arrays.toString(sol.sortArray(new int[]{1}))); // [1]
        System.out.println("Test 4: " + Arrays.toString(sol.sortArray(new int[]{-4,0,7,4,9,-5,-1,0,-7,-1}))); 
    }
}
