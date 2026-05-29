import java.util.*;

/**
 * Problem 37: Where Will the Ball Fall
 * 
 * Grid with diagonal boards (1=right-down, -1=left-down). Drop ball from each column top.
 * Return column where each ball exits, or -1 if stuck.
 *
 * Approach: Simulate each ball. At cell (i,j), check if ball can move diagonally.
 * Ball gets stuck if adjacent cell has opposite direction or hits wall.
 *
 * Time Complexity: O(m * n)
 * Space Complexity: O(n)
 *
 * Production Analogy: Packet routing through a network of one-way redirectors.
 * Similar to load balancer routing decisions at each hop.
 */
public class Problem37_WhereWillTheBallFall {

    public static int[] findBall(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[] result = new int[n];
        for (int col = 0; col < n; col++) {
            int j = col;
            for (int i = 0; i < m; i++) {
                int nj = j + grid[i][j];
                if (nj < 0 || nj >= n || grid[i][nj] != grid[i][j]) { j = -1; break; }
                j = nj;
            }
            result[col] = j;
        }
        return result;
    }

    public static void main(String[] args) {
        int[][] grid = {{1,1,1,-1,-1},{1,1,1,-1,-1},{-1,-1,-1,1,1},{1,1,1,1,-1},{-1,-1,-1,-1,-1}};
        System.out.println("Test 1: " + Arrays.toString(findBall(grid)));
        // [1,-1,-1,-1,-1]
        System.out.println("Test 2: " + Arrays.toString(findBall(new int[][]{{-1}})));
        // [-1]
    }
}
