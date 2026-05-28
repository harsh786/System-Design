/**
 * Problem 25: Dungeon Game
 * 
 * Find minimum initial health to reach bottom-right from top-left.
 * Must maintain health > 0 at all times.
 * 
 * Key: Work backwards from bottom-right.
 * State: dp[i][j] = min health needed at (i,j) to reach end
 * 
 * Time: O(m*n), Space: O(n)
 */
public class Problem25_DungeonGame {

    public static int calculateMinimumHP(int[][] dungeon) {
        int m = dungeon.length, n = dungeon[0].length;
        int[] dp = new int[n + 1];
        java.util.Arrays.fill(dp, Integer.MAX_VALUE);
        dp[n - 1] = 1;
        for (int i = m - 1; i >= 0; i--) {
            for (int j = n - 1; j >= 0; j--) {
                int minNext = Math.min(dp[j], dp[j + 1]);
                dp[j] = Math.max(1, minNext - dungeon[i][j]);
            }
            dp[n] = Integer.MAX_VALUE;
        }
        return dp[0];
    }

    public static void main(String[] args) {
        System.out.println("=== Dungeon Game ===");
        System.out.println(calculateMinimumHP(new int[][]{{-2,-3,3},{-5,-10,1},{10,30,-5}})); // 7
        System.out.println(calculateMinimumHP(new int[][]{{0}})); // 1
    }
}
