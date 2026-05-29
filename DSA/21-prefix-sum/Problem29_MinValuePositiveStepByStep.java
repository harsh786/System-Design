/**
 * Problem 29: Minimum Value to Get Positive Step by Step Sum (LeetCode 1413)
 * 
 * Pattern: Find minimum prefix sum, answer is max(1, 1 - minPrefix)
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Determining minimum initial credit/balance to ensure account
 * never goes negative through a sequence of transactions.
 */
public class Problem29_MinValuePositiveStepByStep {

    public static int minStartValue(int[] nums) {
        int minPrefix = 0, sum = 0;
        for (int n : nums) {
            sum += n;
            minPrefix = Math.min(minPrefix, sum);
        }
        return 1 - minPrefix;
    }

    public static void main(String[] args) {
        assert minStartValue(new int[]{-3, 2, -3, 4, 2}) == 5;
        assert minStartValue(new int[]{1, 2}) == 1;
        assert minStartValue(new int[]{1, -2, -3}) == 5;
        System.out.println("All tests passed!");
    }
}
