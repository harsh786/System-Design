/**
 * Problem 41: Delete and Earn
 * 
 * Delete num to earn num points, but must delete all (num-1) and (num+1).
 * Transform to House Robber on value frequency array.
 * 
 * Time: O(n + max), Space: O(max)
 */
public class Problem41_DeleteAndEarn {

    public static int deleteAndEarn(int[] nums) {
        int max = 0;
        for (int n : nums) max = Math.max(max, n);
        int[] sum = new int[max + 1];
        for (int n : nums) sum[n] += n;
        int prev2 = 0, prev1 = 0;
        for (int i = 1; i <= max; i++) {
            int curr = Math.max(prev1, prev2 + sum[i]);
            prev2 = prev1;
            prev1 = curr;
        }
        return prev1;
    }

    public static void main(String[] args) {
        System.out.println("=== Delete and Earn ===");
        System.out.println(deleteAndEarn(new int[]{3,4,2})); // 6
        System.out.println(deleteAndEarn(new int[]{2,2,3,3,3,4})); // 9
    }
}
