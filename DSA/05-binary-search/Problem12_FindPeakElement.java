/**
 * Problem 12: Find Peak Element
 * 
 * Find any peak (element greater than its neighbors). nums[-1] = nums[n] = -inf.
 * 
 * Approach: Binary search — move toward the higher neighbor (guaranteed peak exists).
 * Invariant: A peak always exists in the direction of the higher neighbor.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding a local maximum in traffic patterns for
 * auto-scaling trigger — any peak suffices for burst detection.
 */
public class Problem12_FindPeakElement {
    public static int findPeakElement(int[] nums) {
        int lo = 0, hi = nums.length - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] > nums[mid + 1]) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(findPeakElement(new int[]{1,2,3,1}));       // 2
        System.out.println(findPeakElement(new int[]{1,2,1,3,5,6,4})); // 5 (or 1)
        System.out.println(findPeakElement(new int[]{1}));              // 0
        System.out.println(findPeakElement(new int[]{1,2}));            // 1
        System.out.println(findPeakElement(new int[]{2,1}));            // 0
    }
}
