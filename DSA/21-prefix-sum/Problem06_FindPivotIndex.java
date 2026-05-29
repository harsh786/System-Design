/**
 * Problem 6: Find Pivot Index (LeetCode 724)
 * 
 * Pattern: Total sum minus running left sum gives right sum; find where left == right
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Finding the partition point in a distributed system where
 * load on left shards equals load on right shards for optimal splitting.
 */
public class Problem06_FindPivotIndex {

    public static int pivotIndex(int[] nums) {
        int total = 0;
        for (int n : nums) total += n;
        int left = 0;
        for (int i = 0; i < nums.length; i++) {
            if (left == total - left - nums[i]) return i;
            left += nums[i];
        }
        return -1;
    }

    public static void main(String[] args) {
        assert pivotIndex(new int[]{1, 7, 3, 6, 5, 6}) == 3;
        assert pivotIndex(new int[]{1, 2, 3}) == -1;
        assert pivotIndex(new int[]{2, 1, -1}) == 0;
        assert pivotIndex(new int[]{0}) == 0;
        System.out.println("All tests passed!");
    }
}
