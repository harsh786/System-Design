/**
 * Problem 27: Maximum Average Subarray I (LeetCode 643)
 * 
 * Approach: Fixed-size sliding window of size k, track sum.
 * Window invariant: window size == k, maximize sum/k.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like computing the best k-minute average throughput
 * for capacity planning reports.
 */
public class Problem27_MaximumAverageSubarrayI {
    public static double findMaxAverage(int[] nums, int k) {
        int sum = 0;
        for (int i = 0; i < k; i++) sum += nums[i];
        int maxSum = sum;
        for (int i = k; i < nums.length; i++) {
            sum += nums[i] - nums[i - k];
            maxSum = Math.max(maxSum, sum);
        }
        return (double) maxSum / k;
    }

    public static void main(String[] args) {
        System.out.println(findMaxAverage(new int[]{1,12,-5,-6,50,3}, 4)); // 12.75
        System.out.println(findMaxAverage(new int[]{5}, 1));                // 5.0
        System.out.println(findMaxAverage(new int[]{-1}, 1));               // -1.0
    }
}
