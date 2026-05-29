/**
 * Problem 12: Reverse Pairs (LeetCode 493)
 * Important reverse pair: nums[i] > 2*nums[j] where i < j
 * 
 * D&C Approach (Modified Merge Sort):
 * - DIVIDE: Split array into halves
 * - CONQUER: Count reverse pairs in each half
 * - COMBINE: Count cross-half pairs, then merge
 *   Key insight: count pairs BEFORE merging while both halves are sorted
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy:
 * - Detecting anomalous price spikes (where later price is less than half of earlier)
 * - Measuring disorder in time-series data streams
 */
public class Problem12_ReversePairs {

    public static int reversePairs(int[] nums) {
        return mergeSort(nums, 0, nums.length - 1);
    }

    private static int mergeSort(int[] nums, int lo, int hi) {
        if (lo >= hi) return 0;
        int mid = lo + (hi - lo) / 2;
        int count = mergeSort(nums, lo, mid) + mergeSort(nums, mid + 1, hi);
        
        // Count cross-half reverse pairs
        int j = mid + 1;
        for (int i = lo; i <= mid; i++) {
            while (j <= hi && (long) nums[i] > 2L * nums[j]) j++;
            count += (j - (mid + 1));
        }
        
        // Standard merge
        int[] temp = new int[hi - lo + 1];
        int i = lo, k = 0;
        j = mid + 1;
        while (i <= mid && j <= hi) {
            if (nums[i] <= nums[j]) temp[k++] = nums[i++];
            else temp[k++] = nums[j++];
        }
        while (i <= mid) temp[k++] = nums[i++];
        while (j <= hi) temp[k++] = nums[j++];
        System.arraycopy(temp, 0, nums, lo, temp.length);
        
        return count;
    }

    public static void main(String[] args) {
        System.out.println(reversePairs(new int[]{1,3,2,3,1}));     // 2
        System.out.println(reversePairs(new int[]{2,4,3,5,1}));     // 3
        System.out.println(reversePairs(new int[]{1,2,3,4}));       // 0
        System.out.println(reversePairs(new int[]{4,3,2,1}));       // 3
        System.out.println(reversePairs(new int[]{2147483647,2147483647,2147483647,2147483647})); // 0
    }
}
