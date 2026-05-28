/**
 * Problem 25: Binary Subarrays With Sum (LeetCode 930)
 * 
 * Approach: exactly(goal) = atMost(goal) - atMost(goal-1)
 * Window invariant: sum of window <= goal.
 * 
 * Time: O(n), Space: O(1)
 * 
 * Production Analogy: Like counting time windows with exactly K successful
 * health checks for availability reporting.
 */
public class Problem25_BinarySubarraysWithSum {
    public static int numSubarraysWithSum(int[] nums, int goal) {
        return atMost(nums, goal) - atMost(nums, goal - 1);
    }

    private static int atMost(int[] nums, int goal) {
        if (goal < 0) return 0;
        int left = 0, sum = 0, count = 0;
        for (int right = 0; right < nums.length; right++) {
            sum += nums[right];
            while (sum > goal) sum -= nums[left++];
            count += right - left + 1;
        }
        return count;
    }

    public static void main(String[] args) {
        System.out.println(numSubarraysWithSum(new int[]{1,0,1,0,1}, 2)); // 4
        System.out.println(numSubarraysWithSum(new int[]{0,0,0,0,0}, 0)); // 15
        System.out.println(numSubarraysWithSum(new int[]{1,1,1}, 2));      // 2
    }
}
