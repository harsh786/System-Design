/**
 * Problem 19: Binary Search (LeetCode 704)
 * 
 * D&C Approach:
 * - DIVIDE: Compare target with middle element
 * - CONQUER: Recurse into left or right half (only one subproblem)
 * - COMBINE: No combine needed - answer propagates up
 * 
 * Recurrence: T(n) = T(n/2) + O(1)
 * Time: O(log n), Space: O(1) iterative / O(log n) recursive
 * 
 * Production Analogy:
 * - B-tree index lookup in databases
 * - Binary search in sorted log files (e.g., finding timestamp range)
 * - Git bisect for finding bug-introducing commit
 */
public class Problem19_BinarySearch {

    public static int binarySearch(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return mid;
            else if (nums[mid] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }

    // Recursive version
    public static int binarySearchRecursive(int[] nums, int target, int lo, int hi) {
        if (lo > hi) return -1;
        int mid = lo + (hi - lo) / 2;
        if (nums[mid] == target) return mid;
        if (nums[mid] < target) return binarySearchRecursive(nums, target, mid + 1, hi);
        return binarySearchRecursive(nums, target, lo, mid - 1);
    }

    public static void main(String[] args) {
        int[] arr = {-1, 0, 3, 5, 9, 12};
        System.out.println(binarySearch(arr, 9));   // 4
        System.out.println(binarySearch(arr, 2));   // -1
        System.out.println(binarySearch(arr, -1));  // 0
        System.out.println(binarySearch(arr, 12));  // 5
        System.out.println(binarySearch(new int[]{5}, 5)); // 0
        System.out.println(binarySearchRecursive(arr, 9, 0, arr.length-1)); // 4
    }
}
