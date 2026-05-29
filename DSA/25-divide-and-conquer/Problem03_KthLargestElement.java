import java.util.Random;

/**
 * Problem 3: Kth Largest Element (Quickselect) - LeetCode 215
 * 
 * D&C Approach (Quickselect):
 * - DIVIDE: Partition array around a pivot
 * - CONQUER: Only recurse into the partition containing kth element (unlike quicksort)
 * - No COMBINE step needed - answer is the pivot when it lands at position k
 * 
 * Recurrence: T(n) = T(n/2) + O(n) average case
 * Time: O(n) average, O(n^2) worst case. With randomized pivot: expected O(n)
 * Space: O(1) with tail recursion optimization
 * 
 * Production Analogy:
 * - Finding P99 latency without sorting all requests
 * - Top-K queries in recommendation engines
 * - Database ORDER BY ... LIMIT K optimization
 */
public class Problem03_KthLargestElement {

    private static Random rand = new Random();

    public static int findKthLargest(int[] nums, int k) {
        int target = nums.length - k; // Convert to kth smallest (0-indexed)
        return quickselect(nums, 0, nums.length - 1, target);
    }

    private static int quickselect(int[] nums, int left, int right, int k) {
        if (left == right) return nums[left];
        
        // Randomized pivot to avoid O(n^2) on sorted input
        int pivotIdx = left + rand.nextInt(right - left + 1);
        pivotIdx = partition(nums, left, right, pivotIdx);
        
        if (pivotIdx == k) return nums[pivotIdx];
        else if (pivotIdx < k) return quickselect(nums, pivotIdx + 1, right, k);
        else return quickselect(nums, left, pivotIdx - 1, k);
    }

    private static int partition(int[] nums, int left, int right, int pivotIdx) {
        int pivotVal = nums[pivotIdx];
        swap(nums, pivotIdx, right); // Move pivot to end
        int storeIdx = left;
        for (int i = left; i < right; i++) {
            if (nums[i] < pivotVal) {
                swap(nums, i, storeIdx);
                storeIdx++;
            }
        }
        swap(nums, storeIdx, right); // Move pivot to final position
        return storeIdx;
    }

    private static void swap(int[] nums, int i, int j) {
        int tmp = nums[i]; nums[i] = nums[j]; nums[j] = tmp;
    }

    public static void main(String[] args) {
        System.out.println(findKthLargest(new int[]{3,2,1,5,6,4}, 2)); // 5
        System.out.println(findKthLargest(new int[]{3,2,3,1,2,4,5,5,6}, 4)); // 4
        System.out.println(findKthLargest(new int[]{1}, 1)); // 1
        System.out.println(findKthLargest(new int[]{7,6,5,4,3,2,1}, 5)); // 3
        System.out.println(findKthLargest(new int[]{2,1}, 1)); // 2
    }
}
