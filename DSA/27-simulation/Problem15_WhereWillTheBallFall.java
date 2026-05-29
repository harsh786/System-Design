/**
 * Problem: Where Will the Ball Fall (LeetCode 1706)
 * Approach: Simulate each ball falling through the grid
 * Complexity: O(m*n) time, O(n) space
 * Production Analogy: Packet routing through network switches with deflection
 */
public class Problem15_WhereWillTheBallFall {
    public int[] findBall(int[][] grid) {
        int n = grid[0].length;
        int[] res = new int[n];
        for (int b = 0; b < n; b++) {
            int col = b;
            for (int[] row : grid) {
                int next = col + row[col];
                if (next < 0 || next >= n || row[next] != row[col]) { col = -1; break; }
                col = next;
            }
            res[b] = col;
        }
        return res;
    }
    public static void main(String[] args) {
        int[][] grid = {{1,1,1,-1,-1},{1,1,1,-1,-1},{-1,-1,-1,1,1},{1,1,1,1,-1},{-1,-1,-1,-1,-1}};
        System.out.println(java.util.Arrays.toString(new Problem15_WhereWillTheBallFall().findBall(grid)));
    }
}
