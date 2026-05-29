/**
 * Problem 29: Find Peak Element (LeetCode 162)
 * 
 * D&C Approach:
 * - DIVIDE: Check middle element
 * - CONQUER: If mid < mid+1, peak must exist in right half (ascending slope)
 *   If mid < mid-1, peak in left half. Otherwise mid is a peak.
 * - Only one subproblem explored (like binary search)
 * 
 * Recurrence: T(n) = T(n/2) + O(1)
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy:
 * - Finding local maxima in time-series data (traffic peaks)
 * - Binary search on monotonicity in optimization problems
 * - Gradient ascent with binary search step
 */
public class Problem29_FindPeakElement {

    public static int findPeakElement(int[] nums) {
        int lo = 0, hi = nums.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] < nums[mid + 1]) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(findPeakElement(new int[]{1, 2, 3, 1}));       // 2
        System.out.println(findPeakElement(new int[]{1, 2, 1, 3, 5, 6, 4})); // 1 or 5
        System.out.println(findPeakElement(new int[]{1}));                 // 0
        System.out.println(findPeakElement(new int[]{1, 2}));             // 1
        System.out.println(findPeakElement(new int[]{2, 1}));             // 0
        System.out.println(findPeakElement(new int[]{1, 2, 3, 4, 5}));   // 4
    }
}
