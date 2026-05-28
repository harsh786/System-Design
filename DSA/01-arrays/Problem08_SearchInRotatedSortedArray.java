/**
 * Problem 8: Search in Rotated Sorted Array
 * Search target in a rotated sorted array. Return index or -1.
 * 
 * Production Analogy: Like searching in a circular buffer / ring buffer where
 * data wraps around - determine which half is sorted, then decide direction.
 * 
 * O(log n) time, O(1) space
 */
public class Problem08_SearchInRotatedSortedArray {

    public static int search(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return mid;
            if (nums[lo] <= nums[mid]) { // left half sorted
                if (target >= nums[lo] && target < nums[mid]) hi = mid - 1;
                else lo = mid + 1;
            } else { // right half sorted
                if (target > nums[mid] && target <= nums[hi]) lo = mid + 1;
                else hi = mid - 1;
            }
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(search(new int[]{4,5,6,7,0,1,2}, 0)); // 4
        System.out.println(search(new int[]{4,5,6,7,0,1,2}, 3)); // -1
        System.out.println(search(new int[]{1}, 0));              // -1
        System.out.println(search(new int[]{1}, 1));              // 0
    }
}
