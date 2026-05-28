/**
 * Problem 33: Single Element in a Sorted Array
 * 
 * Every element appears twice except one. Find the single element.
 * 
 * Approach: Binary search on even indices. Before the single element,
 * pairs start at even indices. After, pairs start at odd indices.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Detecting a corrupted replica in a sorted mirrored
 * storage system where all blocks should be duplicated.
 */
public class Problem33_SingleElementInSortedArray {
    public static int singleNonDuplicate(int[] nums) {
        int lo = 0, hi = nums.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            // Ensure mid is even
            if (mid % 2 == 1) mid--;
            if (nums[mid] == nums[mid + 1]) lo = mid + 2;
            else hi = mid;
        }
        return nums[lo];
    }

    public static void main(String[] args) {
        System.out.println(singleNonDuplicate(new int[]{1,1,2,3,3,4,4,8,8})); // 2
        System.out.println(singleNonDuplicate(new int[]{3,3,7,7,10,11,11}));  // 10
        System.out.println(singleNonDuplicate(new int[]{1}));                  // 1
        System.out.println(singleNonDuplicate(new int[]{1,1,2}));              // 2
    }
}
