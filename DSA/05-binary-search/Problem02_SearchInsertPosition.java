/**
 * Problem 2: Search Insert Position
 * 
 * Given a sorted array and target, return index if found, or where it would be inserted.
 * 
 * Approach: Binary search finding the leftmost position where nums[i] >= target.
 * Invariant: lo always points to the first element >= target after loop.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Inserting a new SLA tier into a sorted list of response-time thresholds.
 */
public class Problem02_SearchInsertPosition {
    public static int searchInsert(int[] nums, int target) {
        int lo = 0, hi = nums.length;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] < target) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }

    public static void main(String[] args) {
        System.out.println(searchInsert(new int[]{1,3,5,6}, 5)); // 2
        System.out.println(searchInsert(new int[]{1,3,5,6}, 2)); // 1
        System.out.println(searchInsert(new int[]{1,3,5,6}, 7)); // 4
        System.out.println(searchInsert(new int[]{1,3,5,6}, 0)); // 0
        System.out.println(searchInsert(new int[]{1}, 0));        // 0
    }
}
