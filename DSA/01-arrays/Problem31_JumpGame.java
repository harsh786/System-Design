/**
 * Problem 31: Jump Game
 * Can you reach the last index? Each element = max jump length.
 * 
 * Production Analogy: Like network hop reachability - can a packet reach the 
 * destination given max TTL decrements at each router?
 * 
 * O(n) time, O(1) space - greedy, track farthest reachable
 */
public class Problem31_JumpGame {

    public static boolean canJump(int[] nums) {
        int farthest = 0;
        for (int i = 0; i < nums.length; i++) {
            if (i > farthest) return false;
            farthest = Math.max(farthest, i + nums[i]);
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.println(canJump(new int[]{2,3,1,1,4})); // true
        System.out.println(canJump(new int[]{3,2,1,0,4})); // false
        System.out.println(canJump(new int[]{0}));           // true
    }
}
