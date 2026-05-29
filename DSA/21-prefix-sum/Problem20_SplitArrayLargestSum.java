/**
 * Problem 20: Split Array Largest Sum (LeetCode 410)
 * 
 * Pattern: Binary search on answer + greedy validation using prefix sums
 * 
 * Binary search the answer (max subarray sum). For each candidate, greedily check
 * if we can split into <= k subarrays each with sum <= candidate.
 * 
 * Time: O(n * log(sum)), Space: O(1)
 * 
 * Production Analogy: Partitioning work across k workers to minimize the maximum
 * load on any single worker (load balancing optimization).
 */
public class Problem20_SplitArrayLargestSum {

    public static int splitArray(int[] nums, int k) {
        int lo = 0, hi = 0;
        for (int num : nums) {
            lo = Math.max(lo, num);
            hi += num;
        }
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (canSplit(nums, k, mid)) hi = mid;
            else lo = mid + 1;
        }
        return lo;
    }

    private static boolean canSplit(int[] nums, int k, int maxSum) {
        int parts = 1, curSum = 0;
        for (int num : nums) {
            if (curSum + num > maxSum) {
                parts++;
                curSum = num;
                if (parts > k) return false;
            } else {
                curSum += num;
            }
        }
        return true;
    }

    public static void main(String[] args) {
        assert splitArray(new int[]{7, 2, 5, 10, 8}, 2) == 18;
        assert splitArray(new int[]{1, 2, 3, 4, 5}, 2) == 9;
        assert splitArray(new int[]{1, 4, 4}, 3) == 4;
        System.out.println("All tests passed!");
    }
}
