/**
 * Problem 49: Range Sum Query - Mutable (LeetCode 307) with Binary Indexed Tree (BIT/Fenwick Tree)
 * 
 * Pattern: BIT provides O(log n) point update and O(log n) prefix sum query.
 * bit[i] stores sum of elements in range determined by lowest set bit of i.
 * 
 * Update: add delta to index, propagate up (i += i & -i)
 * Query prefix sum: accumulate going down (i -= i & -i)
 * 
 * Time: O(log n) per update/query, O(n) build
 * Space: O(n)
 * 
 * Production Analogy: Real-time metrics counters that support both increments and
 * range queries—like updating request counts per endpoint while querying totals
 * across endpoint ranges.
 */
public class Problem49_RangeSumQueryMutable {

    static class NumArray {
        private int[] bit;
        private int[] nums;
        private int n;

        public NumArray(int[] nums) {
            this.n = nums.length;
            this.nums = new int[n];
            this.bit = new int[n + 1];
            for (int i = 0; i < n; i++) update(i, nums[i]);
            System.arraycopy(nums, 0, this.nums, 0, n);
        }

        public void update(int index, int val) {
            int delta = val - nums[index];
            nums[index] = val;
            for (int i = index + 1; i <= n; i += i & (-i))
                bit[i] += delta;
        }

        private int prefixSum(int index) {
            int sum = 0;
            for (int i = index + 1; i > 0; i -= i & (-i))
                sum += bit[i];
            return sum;
        }

        public int sumRange(int left, int right) {
            return prefixSum(right) - (left > 0 ? prefixSum(left - 1) : 0);
        }
    }

    public static void main(String[] args) {
        NumArray na = new NumArray(new int[]{1, 3, 5});
        assert na.sumRange(0, 2) == 9;
        na.update(1, 2);
        assert na.sumRange(0, 2) == 8;
        assert na.sumRange(1, 2) == 7;

        NumArray na2 = new NumArray(new int[]{-1, 0, 1, 2, 3});
        assert na2.sumRange(0, 4) == 5;
        na2.update(0, 5);
        assert na2.sumRange(0, 0) == 5;
        System.out.println("All tests passed!");
    }
}
