/**
 * Problem 41: Max Consecutive Ones (LeetCode 485)
 * 
 * Approach: Simple linear scan tracking current streak.
 * Window invariant: current consecutive 1s count.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding the longest consecutive uptime streak
 * without any interruptions.
 */
public class Problem41_MaxConsecutiveOnes {
    public static int findMaxConsecutiveOnes(int[] nums) {
        int max = 0, count = 0;
        for (int n : nums) {
            if (n == 1) count++;
            else count = 0;
            max = Math.max(max, count);
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(findMaxConsecutiveOnes(new int[]{1,1,0,1,1,1})); // 3
        System.out.println(findMaxConsecutiveOnes(new int[]{1,0,1,1,0,1})); // 2
        System.out.println(findMaxConsecutiveOnes(new int[]{0,0,0}));        // 0
        System.out.println(findMaxConsecutiveOnes(new int[]{1}));            // 1
    }
}
