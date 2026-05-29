import java.util.*;

/**
 * Problem 23: Sort an Array (Heap Sort)
 * 
 * Implement heap sort.
 * 
 * Approach: Build max-heap, repeatedly extract max and place at end.
 * Time Complexity: O(n log n) always
 * Space Complexity: O(1) in-place
 * Stability: Not stable
 * 
 * Production Analogy: Priority-based task scheduler that always processes highest priority first.
 * Used when guaranteed O(n log n) without extra memory is needed (embedded systems).
 */
public class Problem23_SortArrayHeapSort {
    
    public int[] sortArray(int[] nums) {
        int n = nums.length;
        // Build max heap
        for (int i = n / 2 - 1; i >= 0; i--) heapify(nums, n, i);
        // Extract elements
        for (int i = n - 1; i > 0; i--) {
            swap(nums, 0, i);
            heapify(nums, i, 0);
        }
        return nums;
    }
    
    private void heapify(int[] nums, int size, int root) {
        int largest = root;
        int left = 2 * root + 1, right = 2 * root + 2;
        if (left < size && nums[left] > nums[largest]) largest = left;
        if (right < size && nums[right] > nums[largest]) largest = right;
        if (largest != root) {
            swap(nums, root, largest);
            heapify(nums, size, largest);
        }
    }
    
    private void swap(int[] a, int i, int j) { int t = a[i]; a[i] = a[j]; a[j] = t; }
    
    public static void main(String[] args) {
        Problem23_SortArrayHeapSort sol = new Problem23_SortArrayHeapSort();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortArray(new int[]{5,2,3,1}))); // [1,2,3,5]
        System.out.println("Test 2: " + Arrays.toString(sol.sortArray(new int[]{5,1,1,2,0,0}))); // [0,0,1,1,2,5]
        System.out.println("Test 3: " + Arrays.toString(sol.sortArray(new int[]{-1,2,-8,0}))); // [-8,-1,0,2]
    }
}
