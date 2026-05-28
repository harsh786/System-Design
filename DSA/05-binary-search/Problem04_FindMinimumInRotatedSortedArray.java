/**
 * Problem 4: Find Minimum in Rotated Sorted Array
 * 
 * Find the minimum element in a rotated sorted array (no duplicates).
 * 
 * Approach: Binary search comparing mid with hi. If nums[mid] > nums[hi],
 * minimum is in right half; otherwise in left half including mid.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding the oldest entry in a circular time-series buffer.
 */
public class Problem04_FindMinimumInRotatedSortedArray {
    public static int findMin(int[] nums) {
        int lo = 0, hi = nums.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] > nums[hi]) lo = mid + 1;
            else hi = mid;
        }
        return nums[lo];
    }

    public static void main(String[] args) {
        System.out.println(findMin(new int[]{3,4,5,1,2}));   // 1
        System.out.println(findMin(new int[]{4,5,6,7,0,1,2})); // 0
        System.out.println(findMin(new int[]{11,13,15,17}));  // 11
        System.out.println(findMin(new int[]{2,1}));           // 1
        System.out.println(findMin(new int[]{1}));             // 1
    }
}
