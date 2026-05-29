/**
 * Problem 25: Ways to Split Array Into Three Parts (LeetCode 1712)
 * 
 * Pattern: Prefix sum + two pointers to find valid split points where left <= mid <= right
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Partitioning data into three tiers (hot/warm/cold) where
 * each tier's total cost is non-decreasing.
 */
public class Problem25_WaysToSplitArrayIntoThree {

    public static int waysToSplit(int[] nums) {
        int MOD = 1_000_000_007;
        int n = nums.length;
        int[] prefix = new int[n];
        prefix[0] = nums[0];
        for (int i = 1; i < n; i++) prefix[i] = prefix[i - 1] + nums[i];

        int total = prefix[n - 1];
        long count = 0;
        int j = 0, k = 0;
        for (int i = 0; i < n - 2; i++) {
            int left = prefix[i];
            if (left * 3 > total) break;

            j = Math.max(j, i + 1);
            while (j < n - 1 && prefix[j] - left < left) j++;

            k = Math.max(k, j);
            while (k < n - 1 && total - prefix[k] >= prefix[k] - left) k++;

            count = (count + k - j) % MOD;
        }
        return (int) count;
    }

    public static void main(String[] args) {
        assert waysToSplit(new int[]{1, 1, 1}) == 1;
        assert waysToSplit(new int[]{1, 2, 2, 2, 5, 0}) == 3;
        assert waysToSplit(new int[]{3, 2, 1}) == 0;
        System.out.println("All tests passed!");
    }
}
