/**
 * Problem: Game of Life (LeetCode 289)
 * Approach: In-place simulation using state encoding (2=was live now dead, 3=was dead now live)
 * Complexity: O(m*n) time, O(1) space
 * Production Analogy: Cellular automata for distributed system state propagation
 */
public class Problem01_GameOfLife {
    public void gameOfLife(int[][] board) {
        int m = board.length, n = board[0].length;
        int[] dx = {-1,-1,-1,0,0,1,1,1};
        int[] dy = {-1,0,1,-1,1,-1,0,1};
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                int live = 0;
                for (int k = 0; k < 8; k++) {
                    int ni = i+dx[k], nj = j+dy[k];
                    if (ni>=0 && ni<m && nj>=0 && nj<n && (board[ni][nj]==1 || board[ni][nj]==2))
                        live++;
                }
                if (board[i][j]==1 && (live<2 || live>3)) board[i][j]=2;
                else if (board[i][j]==0 && live==3) board[i][j]=3;
            }
        }
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                board[i][j] = board[i][j]==3 ? 1 : (board[i][j]==2 ? 0 : board[i][j]);
    }
    public static void main(String[] args) {
        Problem01_GameOfLife sol = new Problem01_GameOfLife();
        int[][] board = {{0,1,0},{0,0,1},{1,1,1},{0,0,0}};
        sol.gameOfLife(board);
        for (int[] row : board) System.out.println(java.util.Arrays.toString(row));
    }
}
