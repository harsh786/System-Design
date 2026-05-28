/**
 * Problem 39: Missing Element in Sorted Array
 * 
 * Given sorted array with unique elements, find the kth missing number starting from arr[0].
 * 
 * Approach: At index i, missing count = nums[i] - nums[0] - i.
 * Binary search for the index where missing count < k but missing count at i+1 >= k.
 * 
 * Time: O(log n), Space: O(1)
 * 
 * Production Analogy: Finding the kth missing sequence number in a packet
 * stream to identify gaps for retransmission.
 */
public class Problem39_MissingElementInSortedArray {
    public static int missingElement(int[] nums, int k) {
        int n = nums.length;
        // Total missing after last element
        int missingAtEnd = nums[n-1] - nums[0] - (n - 1);
        if (k > missingAtEnd) return nums[n-1] + (k - missingAtEnd);
        
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            int missing = nums[mid] - nums[0] - mid;
            if (missing < k) lo = mid + 1;
            else hi = mid;
        }
        // lo is first index where missing >= k
        // Answer is between nums[lo-1] and nums[lo]
        int missingBefore = nums[lo-1] - nums[0] - (lo - 1);
        return nums[lo-1] + (k - missingBefore);
    }

    public static void main(String[] args) {
        System.out.println(missingElement(new int[]{4,7,9,10}, 1)); // 5
        System.out.println(missingElement(new int[]{4,7,9,10}, 3)); // 8
        System.out.println(missingElement(new int[]{1,2,4}, 3));    // 6
    }
}
