/**
 * Problem 42: Max Consecutive Ones II (LeetCode 487)
 * 
 * Approach: Sliding window allowing at most 1 zero flip.
 * Window invariant: at most 1 zero in window.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like finding longest uptime streak if you could
 * retroactively excuse one outage incident.
 */
public class Problem42_MaxConsecutiveOnesII {
    public static int findMaxConsecutiveOnes(int[] nums) {
        int left = 0, zeros = 0, max = 0;
        for (int right = 0; right < nums.length; right++) {
            if (nums[right] == 0) zeros++;
            while (zeros > 1) {
                if (nums[left] == 0) zeros--;
                left++;
            }
            max = Math.max(max, right - left + 1);
        }
        return max;
    }

    public static void main(String[] args) {
        System.out.println(findMaxConsecutiveOnes(new int[]{1,0,1,1,0}));   // 4
        System.out.println(findMaxConsecutiveOnes(new int[]{1,0,1,1,0,1})); // 4
        System.out.println(findMaxConsecutiveOnes(new int[]{0,0,0}));        // 1
        System.out.println(findMaxConsecutiveOnes(new int[]{1,1,1}));        // 3
    }
}
