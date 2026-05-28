/**
 * Problem 26: Find Minimum in Rotated Sorted Array II (with duplicates)
 * 
 * Approach: Same as Problem 4 but when nums[mid] == nums[hi], shrink hi by 1.
 * 
 * Time: O(n) worst, O(log n) average, Space: O(1)
 * 
 * Production Analogy: Finding earliest event in a circular buffer with duplicate timestamps.
 */
public class Problem26_FindMinimumInRotatedSortedArrayII {
    public static int findMin(int[] nums) {
        int lo = 0, hi = nums.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] > nums[hi]) lo = mid + 1;
            else if (nums[mid] < nums[hi]) hi = mid;
            else hi--; // can't determine, shrink
        }
        return nums[lo];
    }

    public static void main(String[] args) {
        System.out.println(findMin(new int[]{1,3,5}));       // 1
        System.out.println(findMin(new int[]{2,2,2,0,1}));   // 0
        System.out.println(findMin(new int[]{3,3,1,3}));     // 1
        System.out.println(findMin(new int[]{1,1}));          // 1
    }
}
