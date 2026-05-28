import java.util.*;

/**
 * Problem: Surrounded Regions BFS (LeetCode 130)
 * Approach: BFS from border 'O' cells to mark safe ones, then flip rest
 * Time: O(M*N), Space: O(M*N)
 * Production Analogy: Marking externally-reachable services before isolating internal ones
 */
public class Problem48_SurroundedRegionsBFS {
    public void solve(char[][] board) {
        int m = board.length, n = board[0].length;
        Queue<int[]> q = new LinkedList<>();
        for (int i = 0; i < m; i++) { if (board[i][0]=='O') q.offer(new int[]{i,0}); if (board[i][n-1]=='O') q.offer(new int[]{i,n-1}); }
        for (int j = 0; j < n; j++) { if (board[0][j]=='O') q.offer(new int[]{0,j}); if (board[m-1][j]=='O') q.offer(new int[]{m-1,j}); }
        int[][] dirs = {{0,1},{0,-1},{1,0},{-1,0}};
        while (!q.isEmpty()) {
            int[] cell = q.poll();
            if (cell[0]<0||cell[0]>=m||cell[1]<0||cell[1]>=n||board[cell[0]][cell[1]]!='O') continue;
            board[cell[0]][cell[1]] = 'S';
            for (int[] d : dirs) q.offer(new int[]{cell[0]+d[0], cell[1]+d[1]});
        }
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (board[i][j] == 'O') board[i][j] = 'X';
                else if (board[i][j] == 'S') board[i][j] = 'O';
            }
    }

    public static void main(String[] args) {
        char[][] board = {{'X','X','X','X'},{'X','O','O','X'},{'X','X','O','X'},{'X','O','X','X'}};
        new Problem48_SurroundedRegionsBFS().solve(board);
        for (char[] row : board) System.out.println(Arrays.toString(row));
    }
}
