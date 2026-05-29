import java.util.*;

/**
 * Problem 45: Sort Nearly Sorted Array (K-sorted)
 * 
 * Each element is at most k positions away from its sorted position.
 * 
 * Approach: Min-heap of size k+1. Insert elements, extract min to build sorted output.
 * Time Complexity: O(n log k)
 * Space Complexity: O(k)
 * 
 * Production Analogy: Reordering network packets that arrive slightly out of order 
 * (jitter buffer in VoIP/video streaming with bounded reorder distance).
 */
public class Problem45_SortNearlySortedArray {
    
    public int[] sortKSorted(int[] nums, int k) {
        PriorityQueue<Integer> minHeap = new PriorityQueue<>();
        int[] result = new int[nums.length];
        int idx = 0;
        
        for (int i = 0; i < nums.length; i++) {
            minHeap.offer(nums[i]);
            if (minHeap.size() > k) {
                result[idx++] = minHeap.poll();
            }
        }
        while (!minHeap.isEmpty()) {
            result[idx++] = minHeap.poll();
        }
        return result;
    }
    
    public static void main(String[] args) {
        Problem45_SortNearlySortedArray sol = new Problem45_SortNearlySortedArray();
        
        System.out.println("Test 1: " + Arrays.toString(sol.sortKSorted(new int[]{6,5,3,2,8,10,9}, 3)));
        // [2,3,5,6,8,9,10]
        
        System.out.println("Test 2: " + Arrays.toString(sol.sortKSorted(new int[]{2,1,4,3,6,5}, 1)));
        // [1,2,3,4,5,6]
        
        System.out.println("Test 3: " + Arrays.toString(sol.sortKSorted(new int[]{1,2,3}, 0)));
        // [1,2,3] (already sorted, k=0 means heap size 1, just passes through -- Note: k=0 needs k+1=1 heap)
    }
}
