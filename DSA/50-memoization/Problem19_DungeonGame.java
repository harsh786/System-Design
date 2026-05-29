import java.util.*;

public class Problem19_DungeonGame {
    private Integer[][] memo;

    public int calculateMinimumHP(int[][] dungeon) {
        int m = dungeon.length, n = dungeon[0].length;
        memo = new Integer[m][n];
        return helper(dungeon, 0, 0);
    }

    private int helper(int[][] d, int i, int j) {
        if (i >= d.length || j >= d[0].length) return Integer.MAX_VALUE;
        if (i == d.length - 1 && j == d[0].length - 1) return Math.max(1 - d[i][j], 1);
        if (memo[i][j] != null) return memo[i][j];
        int minNext = Math.min(helper(d, i + 1, j), helper(d, i, j + 1));
        memo[i][j] = Math.max(minNext - d[i][j], 1);
        return memo[i][j];
    }

    public static void main(String[] args) {
        Problem19_DungeonGame sol = new Problem19_DungeonGame();
        System.out.println(sol.calculateMinimumHP(new int[][]{{-2,-3,3},{-5,-10,1},{10,30,-5}})); // 7
    }
}
