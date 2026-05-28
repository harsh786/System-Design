/**
 * Problem 3: Search in Rotated Sorted Array
 * 
 * Array was sorted then rotated. No duplicates. Find target index or -1.
 * 
 * Approach: Determine which half is sorted, then decide which half to search.
 * Invariant: At least one half [lo,mid] or [mid,hi] is always sorted.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Searching for a specific log entry in a circular buffer
 * that wraps around — one segment is always in order.
 */
public class Problem03_SearchInRotatedSortedArray {
    public static int search(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return mid;
            // Left half is sorted
            if (nums[lo] <= nums[mid]) {
                if (nums[lo] <= target && target < nums[mid]) hi = mid - 1;
                else lo = mid + 1;
            } else {
                // Right half is sorted
                if (nums[mid] < target && target <= nums[hi]) lo = mid + 1;
                else hi = mid - 1;
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(search(new int[]{4,5,6,7,0,1,2}, 0)); // 4
        System.out.println(search(new int[]{4,5,6,7,0,1,2}, 3)); // -1
        System.out.println(search(new int[]{1}, 0));               // -1
        System.out.println(search(new int[]{3,1}, 1));             // 1
        System.out.println(search(new int[]{5,1,3}, 5));           // 0
    }
}
