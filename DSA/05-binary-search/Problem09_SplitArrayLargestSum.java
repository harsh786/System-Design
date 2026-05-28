/**
 * Problem 9: Split Array Largest Sum
 * 
 * Split array into k subarrays minimizing the largest subarray sum.
 * 
 * Approach: Binary search on the answer [max(nums), sum(nums)].
 * Check if we can split into <= k parts with each part sum <= mid.
 * 
 * Time: O(n * log(sum - max)), Space: O(1)
 * 
 * Production Analogy: Partitioning database shards so that the heaviest
 * shard's load is minimized — balancing partition sizes.
 */
public class Problem09_SplitArrayLargestSum {
    public static int splitArray(int[] nums, int k) {
        int lo = 0, hi = 0;
        for (int n : nums) { lo = Math.max(lo, n); hi += n; }
        
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canSplit(nums, mid, k)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canSplit(int[] nums, int maxSum, int k) {
        int parts = 1, curSum = 0;
        for (int n : nums) {
            if (curSum + n > maxSum) { parts++; curSum = 0; }
            curSum += n;
        }
        return parts <= k;
    }

    public static void main(String[] args) {
        System.out.println(splitArray(new int[]{7,2,5,10,8}, 2)); // 18
        System.out.println(splitArray(new int[]{1,2,3,4,5}, 2));  // 9
        System.out.println(splitArray(new int[]{1,4,4}, 3));       // 4
    }
}
