/**
 * Problem 45: Maximum Average Subarray II (LeetCode 644)
 * 
 * Pattern: Binary search on answer + prefix sum validation.
 * Binary search the average; for each candidate, subtract it from all elements
 * and check if there exists a subarray of length >= k with non-negative sum.
 * 
 * Time: O(n * log((max-min)/epsilon)), Space: O(n)
 * 
 * Production Analogy: Finding the optimal time window (at least k minutes) with
 * highest average throughput for capacity planning reports.
 */
public class Problem45_MaxAverageSubarrayII {

    public static double findMaxAverage(int[] nums, int k) {
        double lo = Integer.MAX_VALUE, hi = Integer.MIN_VALUE;
        for (int n : nums) { lo = Math.min(lo, n); hi = Math.max(hi, n); }

        while (hi - lo > 1e-5) {
            double mid = (lo + hi) / 2;
            if (canAchieve(nums, k, mid)) lo = mid;
            else hi = mid;
        }
        return lo;
    }

    private static boolean canAchieve(int[] nums, int k, double target) {
        // Check if any subarray of length >= k has average >= target
        // Subtract target from each element, find max subarray sum of length >= k
        double sum = 0, prevMin = 0, prevSum = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i] - target;
            if (i >= k - 1) {
                if (sum - prevMin >= 0) return true;
                prevSum += nums[i - k + 1] - target;
                prevMin = Math.min(prevMin, prevSum);
            }
        }
        return false;
    }

    public static void main(String[] args) {
        assert Math.abs(findMaxAverage(new int[]{1, 12, -5, -6, 50, 3}, 4) - 12.75) < 0.001;
        assert Math.abs(findMaxAverage(new int[]{5}, 1) - 5.0) < 0.001;
        assert Math.abs(findMaxAverage(new int[]{-1, -2, -3, -4}, 2) - (-1.5)) < 0.001;
        System.out.println("All tests passed!");
    }
}
