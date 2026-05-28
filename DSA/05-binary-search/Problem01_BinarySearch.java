/**
 * Problem 1: Binary Search
 * 
 * Given a sorted array and a target, return the index of the target or -1.
 * 
 * Approach: Classic binary search with lo/hi pointers converging.
 * Invariant: target, if exists, is always within [lo, hi].
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding a specific configuration version in a sorted
 * deployment history — binary search over timestamped releases.
 */
public class Problem01_BinarySearch {
    public static int search(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) return mid;
            else if (nums[mid] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        System.out.println(search(new int[]{-1,0,3,5,9,12}, 9));   // 4
        System.out.println(search(new int[]{-1,0,3,5,9,12}, 2));   // -1
        System.out.println(search(new int[]{5}, 5));                // 0
        System.out.println(search(new int[]{}, 1));                 // -1 (empty)
        System.out.println(search(new int[]{1,2}, 1));              // 0
        System.out.println(search(new int[]{1,2}, 2));              // 1
    }
}
