/**
 * Problem 5: Longest Increasing Subsequence
 * 
 * State: dp[i] = length of LIS ending at index i
 * Recurrence: dp[i] = max(dp[j] + 1) for all j < i where nums[j] < nums[i]
 * 
 * O(n^2) DP approach + O(n log n) patience sorting approach.
 * 
 * Production Analogy: Like finding the longest chain of dependent deployments
 * where each must be a version upgrade.
 */
public class Problem05_LongestIncreasingSubsequence {

    // O(n^2) DP
    public static int lisDP(int[] nums) {
        if (nums.length == 0) return 0;
        int[] dp = new int[nums.length];
        java.util.Arrays.fill(dp, 1);
        int max = 1;
        for (int i = 1; i < nums.length; i++) {
            for (int j = 0; j < i; j++) {
                if (nums[j] < nums[i]) dp[i] = Math.max(dp[i], dp[j] + 1);
            }
            max = Math.max(max, dp[i]);
        }
        return max;
    }

    // O(n log n) with binary search (patience sorting)
    public static int lisBinarySearch(int[] nums) {
        int[] tails = new int[nums.length];
        int size = 0;
        for (int num : nums) {
            int lo = 0, hi = size;
            while (lo < hi) {
                int mid = (lo + hi) / 2;
                if (tails[mid] < num) lo = mid + 1;
                else hi = mid;
            }
            tails[lo] = num;
            if (lo == size) size++;
        }
        return size;
    }

    public static void main(String[] args) {
        System.out.println("=== LIS ===");
        int[][] tests = {{10,9,2,5,3,7,101,18}, {0,1,0,3,2,3}, {7,7,7,7}};
        for (int[] t : tests) {
            System.out.printf("%s: dp=%d, bs=%d%n",
                java.util.Arrays.toString(t), lisDP(t), lisBinarySearch(t));
        }
    }
}
