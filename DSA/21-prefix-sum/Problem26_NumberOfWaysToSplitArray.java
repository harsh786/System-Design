/**
 * Problem 26: Number of Ways to Split Array (LeetCode 2270)
 * 
 * Pattern: Prefix sum; count indices where leftSum >= rightSum
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding valid partition points for sharding where left shard
 * has at least as much data as right shard.
 */
public class Problem26_NumberOfWaysToSplitArray {

    public static int waysToSplitArray(int[] nums) {
        long total = 0;
        for (int n : nums) total += n;
        long left = 0;
        int count = 0;
        for (int i = 0; i < nums.length - 1; i++) {
            left += nums[i];
            if (left >= total - left) count++;
        }
        return count;
    }

    public static void main(String[] args) {
        assert waysToSplitArray(new int[]{10, 4, -8, 7}) == 2;
        assert waysToSplitArray(new int[]{2, 3, 1, 0}) == 2;
        System.out.println("All tests passed!");
    }
}
