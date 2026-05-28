/**
 * Problem 5: Find First and Last Position of Element in Sorted Array
 * 
 * Approach: Two binary searches — one for leftmost, one for rightmost occurrence.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding the time window (first and last occurrence) of a
 * specific error code in sorted log entries for incident response.
 */
public class Problem05_FindFirstAndLastPosition {
    public static int[] searchRange(int[] nums, int target) {
        return new int[]{findFirst(nums, target), findLast(nums, target)};
    }

    private static int findFirst(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1, result = -1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) { result = mid; hi = mid - 1; }
            else if (nums[mid] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return result;
    }

    private static int findLast(int[] nums, int target) {
        int lo = 0, hi = nums.length - 1, result = -1;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            if (nums[mid] == target) { result = mid; lo = mid + 1; }
            else if (nums[mid] < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return result;
    }

    public static void main(String[] args) {
        print(searchRange(new int[]{5,7,7,8,8,10}, 8)); // [3,4]
        print(searchRange(new int[]{5,7,7,8,8,10}, 6)); // [-1,-1]
        print(searchRange(new int[]{}, 0));               // [-1,-1]
        print(searchRange(new int[]{1}, 1));              // [0,0]
        print(searchRange(new int[]{2,2}, 2));            // [0,1]
    }

    private static void print(int[] r) {
        System.out.println("[" + r[0] + "," + r[1] + "]");
    }
}
