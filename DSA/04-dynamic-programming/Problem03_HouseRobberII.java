/**
 * Problem 3: House Robber II
 * 
 * Houses are arranged in a circle. Cannot rob adjacent houses.
 * 
 * Approach: Since first and last are adjacent, solve two subproblems:
 * 1) Rob houses 0..n-2 (exclude last)
 * 2) Rob houses 1..n-1 (exclude first)
 * Answer = max of both.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Circular dependency resolution - when resources form a ring,
 * break the cycle by considering two linear cases.
 */
public class Problem03_HouseRobberII {

    public static int rob(int[] nums) {
        if (nums.length == 1) return nums[0];
        return Math.max(robRange(nums, 0, nums.length - 2), robRange(nums, 1, nums.length - 1));
    }

    private static int robRange(int[] nums, int start, int end) {
        int prev2 = 0, prev1 = 0;
        for (int i = start; i <= end; i++) {
            int curr = Math.max(prev1, prev2 + nums[i]);
            prev2 = prev1;
            prev1 = curr;
        }
        return prev1;
    }

    public static void main(String[] args) {
        System.out.println("=== House Robber II ===");
        int[][] tests = {{2,3,2}, {1,2,3,1}, {1,2,3}, {0}, {1}};
        for (int[] t : tests) {
            System.out.printf("%s: %d%n", java.util.Arrays.toString(t), rob(t));
        }
    }
}
