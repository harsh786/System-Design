/**
 * Problem 2: Jump Game II (LeetCode 45)
 * 
 * Return the minimum number of jumps to reach the last index.
 *
 * Greedy Choice: At each "level" (BFS-like), jump to the farthest reachable position.
 * Exchange Argument: Jumping farther never increases the number of jumps needed.
 *
 * Time Complexity: O(n)
 * Space Complexity: O(1)
 *
 * Production Analogy: Minimum number of CDN hops to deliver content from origin to edge.
 */
public class Problem02_JumpGameII {
    
    public static int jump(int[] nums) {
        int jumps = 0, curEnd = 0, farthest = 0;
        for (int i = 0; i < nums.length - 1; i++) {
            farthest = Math.max(farthest, i + nums[i]);
            if (i == curEnd) {
                jumps++;
                curEnd = farthest;
            }
        }
        return jumps;
    }
    
    public static void main(String[] args) {
        System.out.println(jump(new int[]{2,3,1,1,4}));  // 2
        System.out.println(jump(new int[]{2,3,0,1,4}));  // 2
        System.out.println(jump(new int[]{1,1,1,1}));    // 3
        System.out.println(jump(new int[]{1}));           // 0
    }
}
