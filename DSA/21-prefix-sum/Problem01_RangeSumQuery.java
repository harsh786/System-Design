/**
 * Problem 1: Range Sum Query - Immutable (LeetCode 303)
 * 
 * Pattern: Basic prefix sum array for O(1) range queries
 * 
 * Concept: Build prefix[i] = sum of nums[0..i-1], then rangeSum(l,r) = prefix[r+1] - prefix[l]
 * 
 * Time Complexity: O(n) build, O(1) per query
 * Space Complexity: O(n)
 * 
 * Production Analogy: Time-series aggregation in monitoring dashboards.
 * When you query "total requests between 2pm-5pm", the system doesn't sum each minute—
 * it uses pre-computed cumulative counters (like Prometheus rate() over counters).
 */
public class Problem01_RangeSumQuery {

    static class NumArray {
        private int[] prefix;

        public NumArray(int[] nums) {
            prefix = new int[nums.length + 1];
            for (int i = 0; i < nums.length; i++) {
                prefix[i + 1] = prefix[i] + nums[i];
            }
        }

        public int sumRange(int left, int right) {
            return prefix[right + 1] - prefix[left];
        }
    }

    public static void main(String[] args) {
        // Test 1: Basic
        NumArray na = new NumArray(new int[]{-2, 0, 3, -5, 2, -1});
        assert na.sumRange(0, 2) == 1 : "Test 1 failed";
        assert na.sumRange(2, 5) == -1 : "Test 2 failed";
        assert na.sumRange(0, 5) == -3 : "Test 3 failed";

        // Test 2: Single element
        NumArray na2 = new NumArray(new int[]{5});
        assert na2.sumRange(0, 0) == 5 : "Test 4 failed";

        // Test 3: All negatives
        NumArray na3 = new NumArray(new int[]{-1, -2, -3});
        assert na3.sumRange(0, 2) == -6 : "Test 5 failed";

        System.out.println("All tests passed!");
    }
}
