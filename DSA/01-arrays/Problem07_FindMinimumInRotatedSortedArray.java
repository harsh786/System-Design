/**
 * Problem 7: Find Minimum in Rotated Sorted Array
 * Array rotated at some pivot, find the minimum element.
 * 
 * Production Analogy: Like finding the restart point in a circular log buffer -
 * binary search on sorted segments to find the discontinuity.
 * 
 * O(log n) time, O(1) space - binary search
 */
public class Problem07_FindMinimumInRotatedSortedArray {

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
        System.out.println(findMin(new int[]{11,13,15,17})); // 11
        System.out.println(findMin(new int[]{2,1}));          // 1
    }
}
