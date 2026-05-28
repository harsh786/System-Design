/**
 * Problem 1: Jump Game (LeetCode 55)
 * 
 * Given an integer array nums, you are initially positioned at the first index.
 * Each element represents your maximum jump length at that position.
 * Return true if you can reach the last index.
 *
 * Greedy Choice: Track the farthest reachable index. At each position, update the max reach.
 * Exchange Argument: If we can reach position i, we can reach all positions <= i. 
 *   Any solution that skips a reachable position can be replaced by one that doesn't.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Network hop reachability - can a packet reach the destination 
 * given maximum TTL at each router?
 */
public class Problem01_JumpGame {
    
    public static boolean canJump(int[] nums) {
        int maxReach = 0;
        for (int i = 0; i < nums.length; i++) {
            if (i > maxReach) return false;
            maxReach = Math.max(maxReach, i + nums[i]);
        }
        return true;
    }
    
    public static void main(String[] args) {
        System.out.println(canJump(new int[]{2,3,1,1,4}));  // true
        System.out.println(canJump(new int[]{3,2,1,0,4}));  // false
        System.out.println(canJump(new int[]{0}));           // true
        System.out.println(canJump(new int[]{2,0,0}));       // true
        System.out.println(canJump(new int[]{1,0,1,0}));     // false
    }
}
