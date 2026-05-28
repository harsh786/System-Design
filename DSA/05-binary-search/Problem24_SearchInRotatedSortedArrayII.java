/**
 * Problem 24: Search in Rotated Sorted Array II (with duplicates)
 * 
 * Approach: Same as Problem 3 but handle nums[lo]==nums[mid]==nums[hi] by lo++.
 * Worst case O(n) due to duplicates, average O(log n).
 * 
 * Time: O(n) worst, O(log n) average, Space: O(1)
 * 
 * Production Analogy: Searching logs with duplicate timestamps in a rotated buffer.
 */
public class Problem24_SearchInRotatedSortedArrayII {
    public static boolean search(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return true;
            // Handle duplicates
            if (nums[lo] == nums[mid] && nums[mid] == nums[hi]) {
                lo++; hi--;
            } else if (nums[lo] <= nums[mid]) {
                if (nums[lo] <= target && target < nums[mid]) hi = mid - 1;
                else lo = mid + 1;
            } else {
                if (nums[mid] < target && target <= nums[hi]) lo = mid + 1;
                else hi = mid - 1;
            }
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(search(new int[]{2,5,6,0,0,1,2}, 0)); // true
        System.out.println(search(new int[]{2,5,6,0,0,1,2}, 3)); // false
        System.out.println(search(new int[]{1,0,1,1,1}, 0));      // true
        System.out.println(search(new int[]{1,1,1,1,1}, 2));      // false
    }
}
