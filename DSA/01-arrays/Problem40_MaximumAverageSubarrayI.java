/**
 * Problem 40: Maximum Average Subarray I
 * Find contiguous subarray of length k with maximum average.
 * 
 * Production Analogy: Like finding the peak k-minute window of average CPU usage
 * for capacity planning - sliding window.
 * 
 * O(n) time, O(1) space - sliding window of fixed size k
 */
public class Problem40_MaximumAverageSubarrayI {

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
    }
}
