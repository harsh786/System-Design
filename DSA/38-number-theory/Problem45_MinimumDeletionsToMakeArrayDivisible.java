package numbertheory;

import java.util.Arrays;

/**
 * Problem 45: Minimum Deletions to Make Array Divisible (LeetCode 2344)
 * 
 * Approach: Find GCD of numsDivide. Find smallest element in nums that divides this GCD.
 * Sort nums, count elements smaller than that.
 * 
 * Time Complexity: O(n log n + m log max)
 * Space Complexity: O(1)
 */
public class Problem45_MinimumDeletionsToMakeArrayDivisible {
    
    public int minOperations(int[] nums, int[] numsDivide) {
        int g = 0;
        for (int v : numsDivide) g = gcd(g, v);
        Arrays.sort(nums);
        for (int i = 0; i < nums.length; i++) {
            if (g % nums[i] == 0) return i;
        }
        return -1;
    }
    
    private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
    
    public static void main(String[] args) {
        Problem45_MinimumDeletionsToMakeArrayDivisible sol = new Problem45_MinimumDeletionsToMakeArrayDivisible();
        System.out.println(sol.minOperations(new int[]{2,3,2,4,3}, new int[]{9,6,9,3,15})); // 2
    }
}
