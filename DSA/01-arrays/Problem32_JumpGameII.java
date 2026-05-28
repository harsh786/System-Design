/**
 * Problem 32: Jump Game II
 * Minimum number of jumps to reach last index.
 * 
 * Production Analogy: Like minimum hops in a network routing table -
 * BFS-like greedy approach to minimize latency (hops).
 * 
 * O(n) time, O(1) space - greedy BFS (level by level)
 */
public class Problem32_JumpGameII {

    public static int jump(int[] nums) {
        int jumps = 0, curEnd = 0, farthest = 0;
        for (int i = 0; i < nums.length - 1; i++) {
            farthest = Math.max(farthest, i + nums[i]);
            if (i == curEnd) { jumps++; curEnd = farthest; }
        }
        return jumps;
    }

    public static void main(String[] args) {
        System.out.println(jump(new int[]{2,3,1,1,4})); // 2
        System.out.println(jump(new int[]{2,3,0,1,4})); // 2
        System.out.println(jump(new int[]{1,2,3}));      // 2
    }
}
