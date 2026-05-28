import java.util.*;

/**
 * Problem 4: Kth Largest Element in an Array
 * 
 * Find the kth largest element (not kth distinct).
 * 
 * Approach 1: QuickSelect (Hoare's partition) - average O(n), worst O(n²)
 * Approach 2: Min-heap of size k - O(n log k)
 * 
 * Time Complexity: O(n) average with QuickSelect
 * Space Complexity: O(1) for QuickSelect, O(k) for heap
 * 
 * Production Analogy: Finding the P99 latency threshold in a stream of request timings
 * for SLA monitoring without sorting entire dataset.
 */
public class Problem04_KthLargestElement {
    
    // QuickSelect approach
    public int findKthLargest(int[] nums, int k) {
        int target = nums.length - k; // kth largest = (n-k)th smallest
        return quickSelect(nums, 0, nums.length - 1, target);
    }
    
    private int quickSelect(int[] nums, int lo, int hi, int target) {
        Random rand = new Random();
        int pivotIdx = lo + rand.nextInt(hi - lo + 1);
        swap(nums, pivotIdx, hi);
        
        int pivot = nums[hi];
        int i = lo;
        for (int j = lo; j < hi; j++) {
            if (nums[j] <= pivot) {
                swap(nums, i++, j);
            }
        }
        swap(nums, i, hi);
        
        if (i == target) return nums[i];
        else if (i < target) return quickSelect(nums, i + 1, hi, target);
        else return quickSelect(nums, lo, i - 1, target);
    }
    
    private void swap(int[] nums, int i, int j) {
        int tmp = nums[i]; nums[i] = nums[j]; nums[j] = tmp;
    }
    
    // Heap approach
    public int findKthLargestHeap(int[] nums, int k) {
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        for (int num : nums) {
            minHeap.offer(num);
            if (minHeap.size() > k) minHeap.poll();
        }
        return minHeap.peek();
    }
    
    public static void main(String[] args) {
        Problem04_KthLargestElement sol = new Problem04_KthLargestElement();
        
        System.out.println("Test 1: " + sol.findKthLargest(new int[]{3,2,1,5,6,4}, 2)); // 5
        System.out.println("Test 2: " + sol.findKthLargest(new int[]{3,2,3,1,2,4,5,5,6}, 4)); // 4
        System.out.println("Test 3: " + sol.findKthLargest(new int[]{1}, 1)); // 1
        System.out.println("Test 4: " + sol.findKthLargestHeap(new int[]{3,2,1,5,6,4}, 2)); // 5
        System.out.println("Test 5: " + sol.findKthLargest(new int[]{-1,-2,-3,-4}, 2)); // -2
    }
}
