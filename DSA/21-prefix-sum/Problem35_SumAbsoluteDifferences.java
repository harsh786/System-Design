/**
 * Problem 35: Sum of Absolute Differences in a Sorted Array (LeetCode 1685)
 * 
 * Pattern: For sorted array, use prefix sums to compute sum of abs differences in O(1) per element.
 * result[i] = nums[i]*i - prefix[i] + (totalSum - prefix[i+1]) - nums[i]*(n-1-i)
 * 
 * Time: O(n), Space: O(n)
 * 
 * Production Analogy: Computing deviation of each data point from all others
 * in sorted metrics for outlier scoring.
 */
import java.util.Arrays;

public class Problem35_SumAbsoluteDifferences {

    public static int[] getSumAbsoluteDifferences(int[] nums) {
        int n = nums.length;
        int[] prefix = new int[n + 1];
        for (int i = 0; i < n; i++) prefix[i + 1] = prefix[i] + nums[i];

        int[] result = new int[n];
        for (int i = 0; i < n; i++) {
            int leftSum = (long) nums[i] * i - prefix[i] > Integer.MAX_VALUE ? 0 : nums[i] * i - prefix[i];
            int rightSum = (prefix[n] - prefix[i + 1]) - nums[i] * (n - 1 - i);
            result[i] = leftSum + rightSum;
        }
        return result;
    }

    public static void main(String[] args) {
        assert Arrays.equals(getSumAbsoluteDifferences(new int[]{2, 3, 5}), new int[]{4, 3, 5});
        assert Arrays.equals(getSumAbsoluteDifferences(new int[]{1, 4, 6, 8, 10}), new int[]{24, 15, 13, 15, 21});
        System.out.println("All tests passed!");
    }
}
